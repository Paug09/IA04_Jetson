# IA04_Jetson

Modèle LLM embarqué proposant un chatbot dans un musée

## Matériel

- Jetson Orin Nano 8Go

## Consignes

**Pipeline global :**

- Entrée : commentaire texte ou audio
- Si audio : transcription automatique
- Analyse par LLM : résumé + extraction de faits
- Structuration des sorties : JSON / tableau
- Calcul ou génération de la note finale
- Affichage des résultats

## Idées

petit modèle préentrainé + RAG (scrapping oeuvre d'un musée + pages wikipédia associés)

## Musée : 
Musée choisi est Louvre