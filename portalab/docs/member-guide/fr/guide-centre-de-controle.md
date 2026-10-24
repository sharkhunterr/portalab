---
slug: guide-centre-de-controle
title: Centre de contrôle
position: 3
help_keys: [incidents, incidents.detail, services, services.detail]
tags: [guide, incidents, maintenances, services]
---
Savoir d'un coup d'œil si tout va bien sur le portail : le centre de contrôle de l'en-tête, les bannières, la page des incidents et l'état des services.

## Le centre de contrôle dans l'en-tête

Dans l'en-tête, à côté de la cloche, une petite icône résume l'état du portail. Son dessin change selon ce qui se passe :

| Icône | Ce qu'elle signale |
|---|---|
| Un cœur qui bat | Tout va bien |
| Le panneau danger | Un ou plusieurs incidents en cours |
| Une clé à molette | Une maintenance en cours, ou prévue dans moins d'un jour |
| Un triangle d'alerte | Des services en difficulté |
| Un mégaphone, dans la couleur de l'annonce | Une ou plusieurs annonces en cours |

Un petit chiffre indique combien il y en a. Quand plusieurs choses se passent en même temps, l'icône les montre à tour de rôle, la plus grave d'abord et plus longtemps.

### Ouvrir le détail

Cliquez sur l'icône : la fenêtre « Centre de contrôle » s'ouvre. Elle peut contenir :

- **Incidents** : chaque incident ouvert, avec sa gravité, son étape et depuis quand ;
- **Maintenances** : celles de la semaine, en cours (avec le temps restant) ou à venir (avec leurs horaires) ;
- **Annonces** : les annonces en cours, **même celles dont vous avez fermé la bannière** ;
- **Services** : « Tous les services fonctionnent » ou le nombre de services en difficulté.

En bas, deux liens mènent à « Statut des services » et à « Tous les incidents ». Cliquez sur un élément pour ouvrir son détail.

![La fenêtre « Centre de contrôle », ouverte depuis son icône dans l'en-tête](shot:controle-fenetre)

> [!NOTE]
> Selon votre portail, la partie « Services » peut ne pas s'afficher pour vous. Les incidents, maintenances et annonces restent visibles.

## Les bannières

Quand quelque chose d'important se passe, une bannière peut s'afficher en haut de toutes les pages. Elle indique ce que c'est, son titre, une ligne de détails, ses dates de début et de fin, et un lien « Détails » ou « En savoir plus ».

### Les trois sortes de bannières

- **Maintenance** : elle apparaît dès la veille (« Maintenance prévue · Commence dans… »), puis pendant la maintenance (« Maintenance en cours · Se termine dans… »). Une barre sous la bannière montre l'avancement.
- **Incident** : « Incident en cours », avec sa gravité (« Mineur », « Majeur », « Critique »), son étape et sa dernière nouvelle. S'il y en a plusieurs, le plus grave passe en premier.
- **Annonce** : un message de l'équipe du portail, dans la couleur de son ton (information, succès, avertissement ou critique).

Toutes les maintenances ou tous les incidents ne s'affichent pas en bannière : c'est l'équipe du portail qui choisit.

### Fermer une bannière

Cliquez sur la petite croix « Masquer cette annonce ».

- Une bannière de **maintenance** ou d'**incident** peut toujours être fermée. Un incident fermé **revient** s'il s'aggrave.
- Certaines **annonces** ne peuvent pas être fermées : l'administrateur a choisi de les garder affichées. Elles n'ont alors pas de croix.
- Une annonce fermée reste consultable dans le centre de contrôle tant qu'elle est en cours.

> [!TIP]
> Une bannière fermée l'est sur l'appareil et le navigateur que vous utilisez. Sur un autre appareil, elle peut s'afficher à nouveau.

### Quand plusieurs services ont un souci

Si plusieurs services sont dégradés ou indisponibles en même temps, un message le dit en haut de la page. La navigation et la recherche fonctionnent toujours.

## La page Incidents

La page [Incidents](/incidents) dit ce qui ne va pas, où on en est et ce qui a été réparé.

- En haut, un résumé : le nombre d'incidents en cours (ou « Tout fonctionne normalement ») et le nombre d'incidents résolus ces 30 derniers jours.
- Les filtres « En cours », « Résolus » et « Tous » trient la liste.
- Chaque incident est une carte : sa gravité, son étape, depuis quand il dure (ou combien de temps il a duré), les « Services touchés » et sa dernière nouvelle.
- Ouvrez un incident pour lire sa « Chronologie » : chaque étape, de sa déclaration à sa résolution.

![La page Incidents, ses sept repères numérotés](shot:controle-incidents)

1. Le résumé : incidents en cours et résolus ces 30 derniers jours.
2. Les filtres « En cours », « Résolus » et « Tous ».
3. La gravité de l'incident.
4. Depuis quand il dure.
5. Son étape.
6. Sa dernière nouvelle.
7. Les « Services touchés ».

Les étapes d'un incident sont : « En analyse », « Identifié », « Sous surveillance », puis « Résolu ».

En bas de la page, la partie « Maintenances prévues » liste les maintenances à venir : quand, combien de temps et ce qu'elles touchent.

## La page des services

La page [Services](/services) (« État des services ») montre comment vont les services du portail.

- En haut, un résumé : « Tout fonctionne », ou le nombre de services en difficulté, d'incidents en cours ou de services en maintenance.
- Les « Incidents en cours » et les « Maintenances prévues » sont rappelés juste en dessous.
- Chaque service a sa carte : son état (disponible, dégradé, indisponible…), une barre de ses **48 dernières heures** et sa disponibilité.

![La page des services, ses cinq repères numérotés](shot:controle-services)

1. Le résumé de l'état des services.
2. Les « Incidents en cours ».
3. L'état d'un service.
4. Sa barre des dernières heures et sa disponibilité.
5. « Ouvrir » et « Détails ».

Dans la barre des 48 heures, chaque trait est une heure : vert quand tout a marché, orange quand il y a eu des ratés, rouge quand le service était surtout coupé, gris sans vérification. Survolez un trait pour voir son heure.

Sur chaque carte :

- « Ouvrir » vous emmène au service, quand il a une adresse publique ;
- « Détails » ouvre sa fiche : disponibilité sur 24 heures, temps d'arrêt, changements récents, incidents et maintenances qui le concernent… Selon vos droits, certaines parties peuvent ne pas s'afficher.

> [!TIP]
> Un service ne marche pas et rien n'est signalé ? Ouvrez un [ticket au support](/support/new) en choisissant le service concerné. Voir [Support](portalab://wiki/guide-support).

## Être prévenu

Selon votre portail et vos [préférences de notification](/settings/notifications), le portail peut aussi vous prévenir :

- d'une maintenance (« Maintenance demain », « Maintenance dans une heure », « Maintenance en cours », reprogrammée ou annulée) ;
- d'un service indisponible, puis de nouveau disponible.

Les réglages sont expliqués dans [Notifications](portalab://wiki/guide-notifications). Le widget « Incidents en cours » peut aussi s'afficher sur votre [accueil](portalab://wiki/guide-accueil).
