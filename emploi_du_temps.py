"""
Bot Discord - Emploi du temps HETIC
Envoie automatiquement l'EDT chaque matin dans #planning
"""

import discord
from discord.ext import tasks
from icalendar import Calendar
from datetime import datetime, date
import pytz
import urllib.request
import os
import asyncio

# ─────────────────────────────────────────
# ⚙️  CONFIGURATION — modifie ces valeurs
# ─────────────────────────────────────────

DISCORD_TOKEN  = "MTQ4MTA3NjAyMTA4MzExNTc0Mg.GWPaR4.Tx-_budmDxXSyfUO2WzBxW-cebYFzZ8SeahbnQ"          # Token du bot Discord
CHANNEL_ID = 1471110169231360184               # ID du salon #planning

# Choix de la source de l'iCal :
# → Option A : fichier local (dépose le .ics à côté du bot)
ICS_FILE = "emploi_du_temps.ics"

# → Option B : URL directe (si l'extranet donne un lien permanent)
# ICS_URL = "https://www.my-hetic.net/.../.ics?token=xxx"
ICS_URL = None

# Heure d'envoi chaque matin (heure de Paris)
SEND_HOUR   = 7
SEND_MINUTE = 30

# ─────────────────────────────────────────

PARIS = pytz.timezone("Europe/Paris")

def get_calendar():
    """Charge le calendrier depuis fichier ou URL."""
    if ICS_URL:
        with urllib.request.urlopen(ICS_URL) as response:
            return Calendar.from_ical(response.read())
    with open(ICS_FILE, "rb") as f:
        return Calendar.from_ical(f.read())

def clean_summary(summary: str) -> str:
    """Nettoie le SUMMARY : garde juste la matière (avant la première virgule)."""
    parts = str(summary).split(",")
    matiere = parts[0].strip()
    # Détecte le type de cours
    if "E-learning" in summary:
        return f"{matiere} *(e-learning)*"
    if "Face à face" in summary or "AFP" in summary or "FAFP" in summary:
        return f"{matiere} *(présentiel)*"
    return matiere

def get_events_today() -> list[dict]:
    """Retourne les événements du jour triés par heure."""
    cal = get_calendar()
    today = datetime.now(PARIS).date()
    events = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART").dt
        dtend   = component.get("DTEND").dt

        # Normalise en datetime avec timezone
        if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
            dtstart = datetime(dtstart.year, dtstart.month, dtstart.day, tzinfo=pytz.UTC)
            dtend   = datetime(dtend.year, dtend.month, dtend.day, tzinfo=pytz.UTC)

        dtstart_paris = dtstart.astimezone(PARIS)
        dtend_paris   = dtend.astimezone(PARIS)

        if dtstart_paris.date() == today:
            location = str(component.get("LOCATION") or "").strip()
            events.append({
                "debut":   dtstart_paris,
                "fin":     dtend_paris,
                "matiere": clean_summary(component.get("SUMMARY")),
                "salle":   location if location else "En ligne",
            })

    return sorted(events, key=lambda e: e["debut"])

def format_message(events: list[dict]) -> str:
    """Formate le message Discord."""
    now    = datetime.now(PARIS)
    jours  = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    mois   = ["janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

    date_str = f"{jours[now.weekday()]} {now.day} {mois[now.month - 1]} {now.year}"

    if not events:
        return f"📅 **{date_str}**\n\n✅ Pas de cours aujourd'hui — bonne journée !"

    lignes = [f"📅 **Emploi du temps — {date_str}**\n"]
    for e in events:
        debut = e["debut"].strftime("%Hh%M")
        fin   = e["fin"].strftime("%Hh%M")
        lignes.append(f"🕐 **{debut} → {fin}** · {e['matiere']}\n   📍 {e['salle']}")

    lignes.append("\n🤖 *Robot fait par Moaze*")
    return "\n".join(lignes)

# ─────────────────────────────────────────
# Bot Discord
# ─────────────────────────────────────────

intents = discord.Intents.default()
client  = discord.Client(intents=intents)

@tasks.loop(minutes=1)
async def check_and_send():
    """Vérifie toutes les minutes si c'est l'heure d'envoyer."""
    now = datetime.now(PARIS)
    if now.hour == SEND_HOUR and now.minute == SEND_MINUTE:
        channel = client.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"[ERREUR] Channel {CHANNEL_ID} introuvable")
            return
        try:
            events  = get_events_today()
            message = format_message(events)
            await channel.send(message)
            print(f"[OK] EDT envoyé le {now.strftime('%d/%m/%Y à %H:%M')}")
        except Exception as e:
            print(f"[ERREUR] {e}")

@client.event
async def on_ready():
    print(f"[BOT] Connecté en tant que {client.user}")
    print(f"[BOT] Envoi quotidien à {SEND_HOUR}h{SEND_MINUTE:02d} heure de Paris")
    check_and_send.start()

client.run(DISCORD_TOKEN)
