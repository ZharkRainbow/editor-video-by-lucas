#!/usr/bin/env python3
"""Chemins du projet. Seul fichier a adapter sur une autre machine."""
from pathlib import Path

RACINE = Path(__file__).parent

# Rushes sources
RUSH_CAMERA = Path.home() / "Downloads/Camera.-1.mp4"
RUSH_ECRAN = Path.home() / "Downloads/Ecran-1.mp4"
RUSH_CONSULTING = Path.home() / "Downloads/Consulting Client - Mastermind Valentin Montage vidéo"

# Sorties de montage
SORTIE_CONSULTING = Path.home() / "Movies/CapCut/Consulting by Lucas to 16,9"
SORTIE_MASTERCLASS = Path.home() / "Movies/CapCut/Valentin Masterclass"

# Ressources
MUSIQUES = Path.home() / "Documents/Musique pour OpusClip/*Musique calme pour montage"
POLICE = Path.home() / "Library/Fonts/ZTNature-MediumItalic.otf"
POLICE_TITRE = Path.home() / "Library/Fonts/ZTNature-Bold.otf"
MODELE_WHISPER = Path.home() / ".cache/whisper-cpp/ggml-large-v3-turbo.bin"
DEEP_FILTER = Path.home() / ".local/bin/deep-filter"

# Charte
JAUNE = "#FAD400"
BLEU = "#2322E0"
BEIGE = "#D4CCBE"
