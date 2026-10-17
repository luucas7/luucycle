# Vérification locale des retours compacts

Depuis la racine du dépôt, avec Python 3 et sa bibliothèque standard :

```bash
python3 -B -m unittest discover -s tests -v
python3 -B tests/benchmark_compact.py
python3 -B skills/luucycle/scripts/doctor.py --self-test
python3 -B skills/luucycle/scripts/roster.py --self-test
python3 -B skills/luucycle/scripts/check_roster.py --self-test
python3 -B skills/luucycle/check_links.py
```

`synthetic_returns.py` est la source unique du scénario : 96 tâches d'une
application fictive, quatre rapports de workers (dont un échec, un blocage et du
travail partiel), trois observations Orca sur quatre attendues, et un relais.
Les IDs de tâche, Dispatch, worker, roster, terminal, worktree, message et Delivery
sont distincts. Aucune issue réelle, donnée privée, session externe ou requête
réseau n'intervient dans ces tests.

Le benchmark sérialise chaque entrée une seule fois en JSON UTF-8 déterministe
(clés triées, séparateurs compacts, une fin de ligne), puis projette **ces mêmes
octets**, sans changer de données entre les deux mesures. La taille projetée
inclut la référence synthétique stable `fixture:<kind>.json`, l'empreinte, les
comptes et les diagnostics supplémentaires. Les octets du fichier brut conservé
ne sont plus envoyés au coordinateur ; ils ne disparaissent pas du stockage.

Les assertions comparent séparément chaque champ critique et chaque contrôle
imbriqué, avec leur représentation JSON, pour chaque élément des deux sorties.
Elles vérifient aussi comptes, erreurs, empreinte et complétude. L'objectif de
réduction de 80 % porte sur la liste de tâches uniquement. Les contrôles ne sont
jamais raccourcis pour améliorer le résultat. Le benchmark imprime le tableau
avant/après ; les mesures synthétiques sont recalculées à chaque exécution.

Les tests CLI retiennent les vrais fichiers JSON dans des répertoires temporaires,
lisent leurs rapports détaillés par ID exact, contrôlent l'empreinte et vérifient
l'absence de modification du fichier source. Les tests de flux couvrent le mode
sans création de fichier utilisable en Audit. Les cas d'échec incluent entrée
mal formée, champ requis absent, champ inconnu, ID ou clé dupliqués, statut inconnu,
erreur non résolue, résultat partiel, compte incohérent et empreinte modifiée.
Un test de non-régression conserve intégralement les deux flux d'un échec Doctor,
y compris une preuve située après le caractère 1 200.

## Repérage des points d'entrée

Ce tableau situe les surfaces inspectées ; les règles restent dans leurs fichiers
propriétaires, sans être recopiées dans les tests.

| Surface | Emplacement précis | Risque de retour volumineux constaté |
| --- | --- | --- |
| Routage et autorisations | `skills/luucycle/SKILL.md`, `RULES.md` | Le routeur charge une seule branche ; RULES possède les approbations et limites |
| Décomposition et sélection | `IMPLEMENT.md`, étape 2 | Développement intégral d'une spec ou d'une liste de tâches avant le plan |
| Rapports Audit et Execution | `IMPLEMENT.md`, étapes 3 et 4 | Rapport exigé sans frontière de retour auparavant ; synthèse après réception complète possible |
| Diagnostic de workers | `IMPLEMENT.md`, étape 6 | Énumérations Orca, livraisons inbox, états et transcriptions de terminal venant du guide chargé |
| Changement de session | `IMPLEMENT.md`, nouvelle étape 7 | Historique ou rapport entier utilisé comme relais au lieu d'un checkpoint |
| Planification amont | `COOK.md`, étapes 4 et 5 | Résultats de spec et tickets ; le contrat s'applique à leur expansion dans IMPLEMENT |
| Doctor | `DOCTOR.md`, « Output » ; `scripts/doctor.py:main`, `check_orca`, `check_roster` | Le JSON complet est imprimé avant la restitution implicite ; trois chemins d'erreur coupaient aussi le diagnostic |
| Roster | `scripts/roster.py:select_agents`, `compact_list`, `emit` | `--json` imprime contrats, candidats ignorés, agents et diagnostics ; les aperçus plan/apply sont des cibles d'approbation à conserver complètes |
| Branches de configuration | `INIT.md`, `ROSTER-LIST.md`, `ROSTER-ADD.md`, `ROSTER-FORMAT.md` | Inventaires et aperçus explicites ; leurs contrats ne sont pas remplacés par le format d'implémentation |
| Tests préexistants | `doctor.py:self_test`, `roster.py:self_test`, `check_roster.py`, `check_links.py`, `check_links2.py` | Auto-tests et vérification de liens ; aucun scénario de volume avant ce changement |

## Portée de la preuve

Le contrat est défini dans [COMPACT.md](../skills/luucycle/COMPACT.md). Les tests
prouvent sa projection, sa conservation des champs déclarés critiques et ses
arrêts sur les fixtures. Ils ne peuvent pas découvrir une information critique
qu'un producteur aurait cachée dans `detail`, vérifier la vérité d'un rapport,
ni remplacer l'approbation et la validation des preuves par le coordinateur.

Le format testé est la frontière normalisée `luucycle.return.v1`, pas le schéma
natif d'une version d'Orca. Un adaptateur natif doit être vérifié sur le guide et
les réponses de cette version avant utilisation ; aucun adaptateur natif certifié
n'est livré ici. Un schéma natif directement présenté au projecteur provoque STOP.

## Observation sur un projet réel — 17 octobre 2026

Un worker Orca 1.4.224, lancé avec GPT-6.1-Sol en effort xhigh (préférences
effectives vérifiées), a exécuté 86 cas unitaires existants dans sept fichiers
d'un projet consommateur local : 86 réussites, aucun échec ni cas ignoré. Les
19 tests du contrat ont également réussi. Neuf scénarios d'erreur explicitement
injectés ont produit les arrêts attendus ; ils ne représentent pas des défauts
observés dans le projet.

La projection de sept enregistrements issus de ces tests réels a donné :

| Entrées identiques | Brut (octets) | Projeté (octets) | Réduction |
| --- | ---: | ---: | ---: |
| Métadonnées et observations des tests sélectionnés | 99 208 | 78 943 | **20,43 %** |

Tous les champs critiques, les IDs et les contrôles imbriqués ont été comparés
exactement, ainsi que les empreintes des sources. Le coordinateur a réexécuté
avec succès le vérificateur sur ces mêmes artefacts, contrôlé l'empreinte du
rapport et confirmé que les états Git des deux dépôts correspondaient à leurs
états initiaux. Le résultat du worker a été accepté, son terminal libéré avec
archivage du transcript, puis sa Delivery acquittée ; aucune livraison ni terminal
réclamable ne restait dans le Run.

Cette observation datée porte sur des sorties normalisées dérivées du projet.
Les sources, journaux et scripts temporaires du consommateur ne sont pas publiés
dans ce dépôt. Les tests synthétiques ci-dessus restent autonomes et reproductibles
sans ce projet. L'adaptateur Orca natif, plusieurs workers, le fallback, la pagination,
la récupération après incident, le gate UI et les écritures externes restent
**non vérifiés en intégration réelle**.

La réduction dépend de la part narrative des données. Les 20,43 % mesurent des
octets de sortie ; ils ne mesurent ni une accélération, ni des tokens, ni le
contexte total d'une session. Le gain sur ce dernier reste à mesurer séparément.
