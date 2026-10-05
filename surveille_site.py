"""Surveille https://voyage.benin.bj/ et prévient par WhatsApp + e-mail quand la
page d'attente « Bientôt disponible » est remplacée par le vrai site.

Usage :
    python surveille_site.py           # vérification normale (toutes les 10 min)
    python surveille_site.py --test    # envoie un WhatsApp + e-mail de test
    python surveille_site.py --bilan   # bilan hebdo « je suis toujours actif »

Configuration par variables d'environnement (voir README.md).
"""
import hashlib
import html
import json
import os
import re
import smtplib
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

URL = "https://voyage.benin.bj/"
FICHIER_ETAT = Path(__file__).with_name("etat.json")
CONFIRMATIONS = 3                # vérifications « ouvert » successives exigées avant la 1re alerte
PAUSE_CONFIRMATION = 120         # secondes entre deux vérifications de confirmation
RAPPEL = timedelta(hours=4)      # rappels tant que la surveillance n'est pas arrêtée
LIEN_ARRET = os.environ.get("LIEN_ARRET", "")

# Comparaisons faites sans accents ni majuscules.
# Présents n'importe où dans la page => le site n'est pas encore ouvert.
SIGNES_ATTENTE = ("bientot disponible", "coming soon", "under construction", "site en construction",
                  "en maintenance", "checking your browser")
# Présents dans le titre => page d'erreur, de protection anti-robot ou serveur par défaut.
SIGNES_ERREUR_TITRE = ("400", "401", "403", "404", "500", "502", "503", "504", "error", "erreur",
                       "not found", "introuvable", "forbidden", "unavailable", "indisponible",
                       "maintenance", "just a moment", "attention required", "access denied",
                       "welcome to nginx", "it works", "index of", "default web site", "test page")


def normaliser(s):
    s = unicodedata.normalize("NFKD", html.unescape(s))
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def analyser():
    """Renvoie (statut, titre, texte visible) avec statut = ouvert | attente | erreur."""
    req = urllib.request.Request(URL, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache", "Pragma": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            hote = urllib.parse.urlparse(r.geturl()).hostname or ""
            brut = r.read().decode("utf-8", "replace")
    except Exception as e:  # site injoignable, 404, 500... : jamais une ouverture
        return "erreur", str(e), ""

    m = re.search(r"<title[^>]*>(.*?)</title>", brut, re.S | re.I)
    titre = " ".join(html.unescape(m.group(1)).split()) if m else ""
    texte = re.sub(r"<(script|style)\b.*?</\1>|<[^>]+>", " ", brut, flags=re.S | re.I)
    texte = " ".join(html.unescape(texte).split())

    if not (hote == "benin.bj" or hote.endswith(".benin.bj")):
        return "erreur", f"redirigé vers un autre domaine : {hote}", texte
    if len(brut) < 100 or any(s in normaliser(titre) for s in SIGNES_ERREUR_TITRE):
        return "erreur", f"page suspecte ({len(brut)} octets, titre « {titre} »)", texte
    if any(s in normaliser(brut) for s in SIGNES_ATTENTE):
        return "attente", titre, texte
    return "ouvert", titre, texte


def confirmer_ouverture():
    """Revérifie plusieurs fois, espacées, pour écarter un bug passager du site."""
    for i in range(2, CONFIRMATIONS + 1):
        time.sleep(PAUSE_CONFIRMATION)
        statut, titre, _ = analyser()
        print(f"Confirmation {i}/{CONFIRMATIONS} : {statut} ({titre})")
        if statut != "ouvert":
            return None
    return titre


def envoyer_whatsapp(texte):
    tel, cle = os.environ.get("WHATSAPP_PHONE"), os.environ.get("WHATSAPP_APIKEY")
    if not (tel and cle):
        raise RuntimeError("WhatsApp non configuré (WHATSAPP_PHONE / WHATSAPP_APIKEY)")
    url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
        {"phone": tel, "text": texte, "apikey": cle})
    with urllib.request.urlopen(url, timeout=60) as r:
        reponse = r.read().decode("utf-8", "replace")
        if r.status != 200 or "color:red" in reponse:  # CallMeBot signale ses erreurs en rouge
            raise RuntimeError(f"CallMeBot a refusé : {re.sub('<[^>]+>', ' ', reponse).strip()}")
    print("WhatsApp envoyé")


def envoyer_mail(sujet, texte):
    user, mdp, dest = (os.environ.get(k) for k in ("SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"))
    if not (user and mdp and dest):
        raise RuntimeError("E-mail non configuré (SMTP_USER / SMTP_PASSWORD / MAIL_TO)")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = sujet, user, dest
    msg.set_content(texte)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, mdp)
        s.send_message(msg)
    print("E-mail envoyé")


def alerter(sujet, texte):
    """WhatsApp en priorité, puis e-mail. Renvoie (nb réussis, nb échecs)."""
    if LIEN_ARRET:
        texte += f"\n\nPour arrêter la surveillance (sans rien supprimer) : {LIEN_ARRET}"
    ok = ko = 0
    for envoi in (lambda: envoyer_whatsapp(f"{sujet}\n\n{texte}"), lambda: envoyer_mail(sujet, texte)):
        try:
            envoi()
            ok += 1
        except Exception as e:  # un canal en panne ne doit pas bloquer l'autre
            ko += 1
            print(f"Échec d'envoi : {e}")
    return ok, ko


def main():
    etat = json.loads(FICHIER_ETAT.read_text("utf-8")) if FICHIER_ETAT.exists() else {}
    maintenant = datetime.now(timezone.utc)
    ok = ko = 0

    if "--test" in sys.argv:
        ok, ko = alerter("🧪 Test Alerte vol Bénin", "Ceci est un test : tes alertes fonctionnent.")
        sys.exit(1 if ko else 0)

    statut, titre, texte = analyser()
    print(f"Statut : {statut} ({titre})")

    if statut == "ouvert":
        dernier = etat.get("derniere_alerte")
        premiere = not etat.get("ouvert_le")
        if dernier and maintenant - datetime.fromisoformat(dernier) < RAPPEL:
            print("Déjà alerté récemment, prochain rappel plus tard.")
        elif premiere and (titre := confirmer_ouverture()) is None:
            print("Ouverture non confirmée : fausse alerte évitée.")
        else:
            sujet = ("🚨 voyage.benin.bj est OUVERT !" if premiere
                     else "🔔 Rappel : voyage.benin.bj est toujours ouvert")
            ok, ko = alerter(sujet, f"La page « Bientôt disponible » a été remplacée.\n"
                                    f"Titre du site : {titre}\nRéserve ton billet : {URL}")
            if ok:
                etat.setdefault("ouvert_le", maintenant.isoformat())
                etat["derniere_alerte"] = maintenant.isoformat()

    elif statut == "attente":
        etat.pop("ouvert_le", None)      # site refermé : la prochaine ouverture sera ré-annoncée
        etat.pop("derniere_alerte", None)
        empreinte = hashlib.sha256(texte.encode()).hexdigest()
        if etat.get("empreinte") and etat["empreinte"] != empreinte:
            ok, ko = alerter("ℹ️ La page d'attente de voyage.benin.bj a changé",
                             f"Le site n'est PAS encore ouvert, mais son texte a changé "
                             f"(peut-être une date annoncée) :\n\n{texte[:500]}\n\n{URL}")
        if not etat.get("empreinte") or ok:
            etat["empreinte"] = empreinte

    # Bilan hebdo : au 1er passage du lundi après 7h UTC (9h à Paris l'été), quel que soit
    # l'horaire réel du passage, car GitHub ne garantit pas l'heure des tâches planifiées.
    dernier_bilan = etat.get("dernier_bilan")
    bilan_du = (maintenant.weekday() == 0 and maintenant.hour >= 7
                and (not dernier_bilan or datetime.fromisoformat(dernier_bilan).date() != maintenant.date()))
    if statut != "ouvert" and ("--bilan" in sys.argv or bilan_du):
        b_ok, b_ko = alerter("✅ Alerte vol Bénin : surveillance active",
                             f"Je surveille toujours {URL} toutes les 10 minutes.\n"
                             f"État actuel : {statut} ({titre}).")
        ok, ko = ok + b_ok, ko + b_ko
        if b_ok:
            etat["dernier_bilan"] = maintenant.isoformat()

    FICHIER_ETAT.write_text(json.dumps(etat, indent=2, ensure_ascii=False) + "\n", "utf-8")
    sys.exit(1 if ko else 0)  # en cas d'échec d'envoi, GitHub t'envoie aussi un e-mail


if __name__ == "__main__":
    main()
