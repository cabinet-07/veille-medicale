#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille médicale automatique — exécution cloud (GitHub Actions)

Tâches :
- Tous les jours : collecte PubMed, résumé Groq, envoi email
- Mardi & vendredi : génère un épisode podcast MP3 de ~20 min,
  l'ajoute au flux RSS et le pousse sur GitHub Pages

Variables d'environnement requises (secrets GitHub) :
  GROQ_API_KEY          - Clé API Groq (gratuite sur console.groq.com)
  SMTP_USER             - Adresse Gmail expéditrice
  SMTP_PASSWORD         - Mot de passe d'application Gmail
  MAIL_TO               - Adresse destinataire
  PODCAST_BASE_URL      - URL publique du flux (ex: https://USER.github.io/veille-medicale-cloud)
"""

import os
import sys
import json
import asyncio
import smtplib
import logging
import requests
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

import edge_tts

# ============================================================
# CONFIGURATION
# ============================================================
JOURS_RECULS = 2            # 2 jours pour rattraper le week-end
ARTICLES_PAR_THEME = 7
GROQ_MODEL = "llama-3.3-70b-versatile"  # ou "llama-3.1-70b-versatile"

# Dossiers
ROOT = Path(__file__).resolve().parent.parent
PODCAST_DIR = ROOT / "podcast"
EPISODES_DIR = PODCAST_DIR / "episodes"
EPISODES_DIR.mkdir(parents=True, exist_ok=True)
FEED_PATH = PODCAST_DIR / "feed.xml"

# Logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("veille")

# ============================================================
# REQUÊTES PUBMED
# ============================================================
PUBMED_QUERIES = {
    "Médecine générale & interne": (
        '("general practice"[MeSH] OR "internal medicine"[MeSH] OR '
        '"primary health care"[MeSH] OR "family practice"[MeSH]) '
        'AND (review[pt] OR randomized controlled trial[pt] OR '
        'meta-analysis[pt] OR guideline[pt])'
    ),
    "Robotique humanoïde & prothèses": (
        '("artificial limbs"[MeSH] OR "robotics"[MeSH] OR '
        '"prosthesis design"[MeSH] OR "exoskeleton"[tiab] OR '
        '"humanoid"[tiab] OR "bionic"[tiab] OR '
        '"brain-computer interface"[tiab] OR "neural prosthesis"[tiab])'
    ),
    "Thérapies innovantes": (
        '("gene therapy"[MeSH] OR "cell- and tissue-based therapy"[MeSH] OR '
        '"immunotherapy"[MeSH] OR "CRISPR"[tiab] OR "mRNA vaccine"[tiab] OR '
        '"CAR-T"[tiab] OR "personalized medicine"[MeSH]) '
        'AND (clinical trial[pt] OR review[pt])'
    ),
}

def pubmed_search(query, days_back, retmax):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    date_filter = f' AND ("last {days_back} days"[edat])'
    try:
        r = requests.get(f"{base}/esearch.fcgi", params={
            "db": "pubmed", "term": query + date_filter,
            "retmax": retmax, "sort": "date", "retmode": "json",
        }, timeout=30)
        r.raise_for_status()
        pmids = r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        log.warning(f"Echec esearch: {e}")
        return []
    if not pmids:
        return []
    try:
        r = requests.get(f"{base}/efetch.fcgi", params={
            "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
        }, timeout=30)
        r.raise_for_status()
        if not r.text.strip().startswith("<"):
            log.warning(f"Reponse efetch non-XML: {r.text[:200]}")
            return []
        root = ET.fromstring(r.text)
    except Exception as e:
        log.warning(f"Echec efetch/parse: {e}")
        return []
    articles = []
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext(".//PMID") or ""
        title = art.findtext(".//ArticleTitle") or ""
        abstract = " ".join(
            (e.text or "") for e in art.findall(".//Abstract/AbstractText")
        ).strip()
        journal = art.findtext(".//Journal/Title") or ""
        year = art.findtext(".//PubDate/Year") or ""
        pub_types = [e.text or "" for e in art.findall(".//PublicationType")]
        if title and abstract:
            articles.append({
                "title": title, "abstract": abstract,
                "journal": journal, "year": year,
                "pmid": pmid, "pub_types": pub_types,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
    import time
    time.sleep(0.4)
    return articles



# ============================================================
# RÉSUMÉ via GROQ (gratuit)
# ============================================================
def groq_chat(prompt, max_tokens=4000):
    """Appelle Groq API. Doc : https://console.groq.com/docs"""
    api_key = os.environ["GROQ_API_KEY"]
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def generer_email_html(donnees):
    """Email technique direct, sans introduction inutile, ~1000 mots."""
    payload = []
    for theme, articles in donnees.items():
        if not articles:
            continue
        payload.append(f"\n### {theme}")
        for i, a in enumerate(articles, 1):
            payload.append(
                f"\n[{i}] {a['title']}\n"
                f"Journal: {a['journal']} ({a['year']})\n"
                f"Type: {', '.join(a.get('pub_types', []))}\n"
                f"URL: {a['url']}\n"
                f"Abstract: {a['abstract'][:1500]}"
            )
    payload_text = "\n".join(payload)

    prompt = f"""Tu es rédacteur scientifique médical. Génère un email HTML de veille médicale technique en français.

REGLES IMPERATIVES :
- AUCUNE phrase d'introduction ni de blabla ("Voici votre veille", "Bonjour", etc.)
- AUCUNE conclusion ni signature
- Commencer DIRECTEMENT par le contenu utile
- Niveau TECHNIQUE : terminologie médicale précise, pas de vulgarisation
- Mentionner systématiquement : type d'étude, taille d'échantillon si dispo, niveau de preuve, p-value ou IC95% si rapporté, implication clinique concrète
- Total : ~1000 mots, lisible en 5 minutes

STRUCTURE HTML (utiliser uniquement <h2>, <h3>, <p>, <strong>, <em>, <a>, <ul>, <li>) :

<h2>Points clés</h2>
<ul>
  <li>3 puces avec les 3 informations les plus importantes du jour, toutes catégories confondues</li>
</ul>

<h2>Médecine générale et interne</h2>
Pour chaque article retenu, un paragraphe :
<p><strong>Titre traduit en français</strong> (<em>nom du journal</em>) — Synthèse technique en 3-4 phrases. <a href="URL">PubMed</a></p>

<h2>Robotique humanoïde et prothèses</h2>
Idem.

<h2>Thérapies innovantes</h2>
Idem.

Sélectionne 3 à 5 articles MAX par section, les plus pertinents (méta-analyses, RCT, guidelines en priorité). Ignore les articles peu intéressants.

ARTICLES :
{payload_text}

Génère UNIQUEMENT le HTML, sans balises <html>, <body>, ni explication."""

    return groq_chat(prompt, max_tokens=4000)


def generer_script_audio(donnees):
    """Script narratif pour podcast de 20 min ~2800 mots, niveau technique."""
    payload = []
    for theme, articles in donnees.items():
        if not articles:
            continue
        payload.append(f"\n=== {theme} ===")
        for a in articles:
            payload.append(
                f"\n- {a['title']}\n  Journal: {a['journal']} ({a['year']})\n"
                f"  Type: {', '.join(a.get('pub_types', []))}\n"
                f"  Abstract: {a['abstract'][:1500]}"
            )
    payload_text = "\n".join(payload)

    date_fr = datetime.now().strftime("%d %B %Y")

    prompt = f"""Tu rédiges le SCRIPT ORAL d'un podcast de veille médicale technique francophone, épisode du {date_fr}.

DUREE CIBLE : 20 minutes (environ 2800 mots, débit 140 mots/minute).

CONTRAINTES DE STYLE :
- Niveau TECHNIQUE médical : terminologie précise, on parle à des médecins
- Phrases courtes et fluides, pour être lues à voix haute
- Transitions naturelles entre les sujets ("Passons maintenant à...", "Du côté de...")
- AUCUNE liste à puces, AUCUN titre, AUCUN markdown — texte oral continu
- Pas d'URL ni de DOI à l'oral, juste le nom du journal et l'année
- Pour chaque étude : contexte clinique, méthodologie, résultats chiffrés (p, IC95%, NNT...), implication pour la pratique

DEBUT IMPERATIF : "Bonjour, voici votre veille médicale du {date_fr}."
FIN IMPERATIVE : "C'était votre veille médicale, bonne journée."

STRUCTURE :
1. Médecine générale et interne (8-10 min, ~5 études les plus pertinentes)
2. Robotique humanoïde et prothèses (4-5 min, ~3 développements)
3. Thérapies innovantes (5-6 min, ~4 études)

ARTICLES (sélectionne les plus pertinents, ignore le bruit) :
{payload_text}

Écris UNIQUEMENT le script à lire à voix haute, sans aucune autre indication ni guillemet."""

    return groq_chat(prompt, max_tokens=6000)


# ============================================================
# AUDIO TTS (Edge TTS gratuit)
# ============================================================
async def generer_audio_async(texte, fichier, voix="fr-FR-HenriNeural"):
    communicate = edge_tts.Communicate(texte, voix)
    await communicate.save(str(fichier))


def generer_audio(texte, fichier):
    asyncio.run(generer_audio_async(texte, fichier))


# ============================================================
# FLUX PODCAST RSS
# ============================================================
def initialiser_feed():
    """Crée le feed.xml initial si absent."""
    if FEED_PATH.exists():
        return
    base_url = os.environ.get("PODCAST_BASE_URL", "")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Veille médicale personnelle</title>
    <link>{base_url}</link>
    <language>fr-fr</language>
    <description>Veille médicale automatique — médecine générale, robotique humanoïde, thérapies innovantes. Épisodes le mardi et vendredi.</description>
    <itunes:author>Veille médicale</itunes:author>
    <itunes:summary>Veille médicale automatique technique francophone, publiée le mardi et vendredi.</itunes:summary>
    <itunes:explicit>false</itunes:explicit>
    <itunes:category text="Health &amp; Fitness">
      <itunes:category text="Medicine"/>
    </itunes:category>
  </channel>
</rss>
"""
    FEED_PATH.write_text(feed, encoding="utf-8")


def ajouter_episode_au_feed(fichier_mp3, titre, description, duree_secondes):
    """Ajoute un nouvel item au flux RSS."""
    initialiser_feed()
    base_url = os.environ.get("PODCAST_BASE_URL", "").rstrip("/")
    mp3_url = f"{base_url}/episodes/{fichier_mp3.name}"
    taille = fichier_mp3.stat().st_size

    # Lire le feed existant
    tree = ET.parse(FEED_PATH)
    root = tree.getroot()
    channel = root.find("channel")

    # Construire le nouvel item (en string pour gérer correctement les namespaces)
    pub_date = formatdate(timeval=None, localtime=False, usegmt=True)
    guid = fichier_mp3.stem

    item_xml = f"""<item>
      <title>{xml_escape(titre)}</title>
      <description>{xml_escape(description)}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
      <enclosure url="{mp3_url}" length="{taille}" type="audio/mpeg"/>
      <itunes:duration>{int(duree_secondes)}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""

    # Insérer le nouvel item juste après la description du channel
    item_element = ET.fromstring(item_xml)
    # Trouver la dernière balise non-item du channel et insérer après
    insert_index = 0
    for i, child in enumerate(channel):
        if child.tag != "item":
            insert_index = i + 1
        else:
            break
    channel.insert(insert_index, item_element)

    # Garder seulement les 50 derniers épisodes
    items = channel.findall("item")
    if len(items) > 50:
        for old in items[50:]:
            channel.remove(old)

    # Enregistrer (en ré-enregistrant les namespaces correctement)
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")
    tree.write(FEED_PATH, encoding="utf-8", xml_declaration=True)


def estimer_duree_mp3(fichier):
    """Estimation grossière de la durée (1 Mo ≈ 60s à 128 kbps)."""
    taille_mo = fichier.stat().st_size / (1024 * 1024)
    return int(taille_mo * 60)


# ============================================================
# ENVOI EMAIL
# ============================================================
def envoyer_email(html_body, sujet):
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_USER"]
    msg["To"] = os.environ["MAIL_TO"]
    msg["Subject"] = sujet
    msg.set_content("Cet email contient une version HTML.")
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(msg)
    log.info(f"Email envoyé à {os.environ['MAIL_TO']}")


# ============================================================
# ORCHESTRATION
# ============================================================
def run():
    today = datetime.now()
    # weekday : 0=lundi ... 6=dimanche
    is_audio_day = today.weekday() in (1, 4)  # mardi & vendredi
    mode = os.environ.get("RUN_MODE", "auto")
    if mode == "email":
        is_audio_day = False
    elif mode == "audio":
        is_audio_day = True

    log.info(f"Date: {today.strftime('%A %d/%m/%Y')} | Mode: {mode} | Audio: {is_audio_day}")

    # 1. Collecte
    donnees = {}
    for theme, query in PUBMED_QUERIES.items():
        log.info(f"PubMed -> {theme}")
        articles = pubmed_search(query, JOURS_RECULS, ARTICLES_PAR_THEME * 2)
        # Tri : favorise méta-analyses, RCT, guidelines
        def score(a):
            t = " ".join(a.get("pub_types", [])).lower()
            s = 0
            if "meta-analysis" in t: s += 10
            if "guideline" in t: s += 8
            if "randomized controlled trial" in t: s += 6
            if "review" in t: s += 3
            return s
        articles.sort(key=score, reverse=True)
        donnees[theme] = articles[:ARTICLES_PAR_THEME]
        log.info(f"  -> {len(donnees[theme])} articles retenus")

    if not any(donnees.values()):
        log.warning("Aucun article trouvé, fin.")
        return

    # 2. Email quotidien
    log.info("Génération email...")
    html = generer_email_html(donnees)
    # Wrap HTML body
    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{{font-family:-apple-system,Segoe UI,sans-serif;max-width:720px;margin:20px auto;padding:0 15px;color:#222;line-height:1.5}}
  h2{{color:#0066cc;border-bottom:1px solid #ddd;padding-bottom:5px;margin-top:25px}}
  h3{{color:#333}}
  a{{color:#0066cc}}
  ul{{padding-left:20px}}
</style>
</head><body>
{html}
<hr><p style="color:#888;font-size:12px">Veille médicale — {today.strftime('%d/%m/%Y')}</p>
</body></html>"""

    sujet = f"Veille médicale — {today.strftime('%d/%m/%Y')}"
    envoyer_email(full_html, sujet)

    # 3. Podcast (mardi/vendredi)
    if is_audio_day:
        log.info("Génération script audio...")
        script = generer_script_audio(donnees)

        nom_fichier = f"veille_{today.strftime('%Y%m%d')}.mp3"
        chemin_mp3 = EPISODES_DIR / nom_fichier
        log.info(f"Génération MP3 -> {chemin_mp3}")
        generer_audio(script, chemin_mp3)

        # Métadonnées du flux
        titre = f"Veille médicale du {today.strftime('%d/%m/%Y')}"
        # Description = points clés extraits du script (premières lignes après l'intro)
        lignes = script.split(".")
        description = ". ".join(lignes[1:6]).strip()[:500] + "..."
        duree = estimer_duree_mp3(chemin_mp3)

        log.info("Mise à jour du flux RSS...")
        ajouter_episode_au_feed(chemin_mp3, titre, description, duree)

        log.info(f"✅ Épisode publié : {chemin_mp3}")

    log.info("✅ Terminé")


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        log.exception(f"Erreur fatale : {e}")
        sys.exit(1)
