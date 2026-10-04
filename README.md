# Alerte vol Bénin

Surveille https://voyage.benin.bj/ toutes les 10 minutes (via GitHub Actions,
gratuit, aucun ordinateur à laisser allumé) et prévient **par WhatsApp puis
par e-mail** dès que la page « Bientôt disponible » est remplacée par le vrai site.

## Ce que tu reçois

| Message | Quand |
|---|---|
| 🚨 **Le site est OUVERT !** | Ouverture confirmée par 3 vérifications espacées de 2 min |
| 🔔 Rappel | Toutes les 4 h tant que le site est ouvert et que tu n'as pas arrêté la surveillance |
| ℹ️ La page d'attente a changé | Le texte d'attente a été modifié (ex. une date annoncée), **sans** ouverture |
| ✅ Bilan hebdo | Chaque lundi vers 9h : preuve que la surveillance tourne toujours |

## Protection contre les fausses alertes

Le site n'est déclaré ouvert **que si toutes ces conditions sont réunies, 3 fois de suite
à 2 minutes d'intervalle** :

- la page répond normalement (pas d'erreur 404/500/503, pas de délai dépassé) ;
- elle reste sur un domaine `benin.bj` (pas de redirection vers un site parking) ;
- elle n'est pas vide, ni une page d'erreur, de maintenance, de protection anti-robot
  (Cloudflare) ou de serveur par défaut ;
- elle ne contient plus « Bientôt disponible », « Coming soon », « en construction »
  ou « en maintenance » (accents, majuscules et codes HTML ignorés).

Un incident passager du site ne déclenche donc jamais d'alerte.

## Installation (une seule fois)

### 1. Clé WhatsApp (gratuite, CallMeBot)

1. Enregistre le contact **+34 644 05 92 17** dans ton téléphone
   (vérifie le numéro à jour sur https://www.callmebot.com/blog/free-api-whatsapp-messages/).
2. Envoie-lui sur WhatsApp exactement : `I allow callmebot to send me messages`
3. Tu reçois ta clé API (`apikey`) en moins de 2 minutes.

### 2. Mot de passe d'application Gmail

1. Active la validation en 2 étapes sur ton compte Google.
2. Crée un mot de passe d'application sur https://myaccount.google.com/apppasswords
   (16 lettres, à utiliser à la place de ton vrai mot de passe).

### 3. Secrets GitHub

Dans le dépôt : **Settings → Secrets and variables → Actions → New repository secret**.
Les secrets sont chiffrés et invisibles, même si le dépôt est public.

| Nom | Valeur |
|---|---|
| `WHATSAPP_PHONE` | ton numéro au format international, ex. `+33612345678` |
| `WHATSAPP_APIKEY` | la clé reçue de CallMeBot |
| `SMTP_USER` | ton adresse Gmail |
| `SMTP_PASSWORD` | le mot de passe d'application Gmail |
| `MAIL_TO` | l'adresse qui reçoit les alertes |

### 4. Test

**Actions → Surveillance voyage.benin.bj → Run workflow → mode `test`**.
Tu dois recevoir un WhatsApp et un e-mail. Si un envoi échoue, le passage apparaît
en rouge et GitHub t'envoie un e-mail avec le détail.

## Arrêter la surveillance (sans rien supprimer)

Une fois ton billet pris :

1. Ouvre **Actions → Surveillance voyage.benin.bj** (le lien est aussi en bas de
   chaque alerte).
2. Clique sur **⋯** en haut à droite → **Disable workflow**.

Plus aucun message n'est envoyé, mais tout est conservé. Pour relancer plus tard
(prochains vols) : même endroit → **Enable workflow**.
