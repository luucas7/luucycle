# Vérification locale des retours compacts

Depuis la racine du dépôt, avec Python 3 et sa bibliothèque standard :

```bash
export PYTHONDONTWRITEBYTECODE=1
python3 -B -m unittest discover -s tests -v
python3 -B tests/benchmark_compact.py
python3 -B skills/luucycle/scripts/doctor.py --self-test
python3 -B skills/luucycle/scripts/roster.py --self-test
python3 -B skills/luucycle/scripts/check_roster.py --self-test
python3 -B skills/luucycle/scripts/check_skill_hygiene.py skills/luucycle
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

La suite de tests comportementaux (`behavioral_trace.py` et `test_behavioral_trace.py`)
assure la vérification déterministe d'invariants d'orchestration :
- **Zéro prompt post-settlement** (`zero_post_settlement_prompts`) : aucune relance ou sollicitation du worker après le règlement ou l'arrêt de la tâche.
- **Libération immédiate des terminaux** (`immediate_terminal_release`) : libération sans délai du terminal et de la session dès la fin du travail.
- **Respect du compact return** (`projection_boundary_respect`) : consommation de la projection compacte par le coordinateur sans inspection injustifiée des payloads détaillés.

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
| Branches de configuration | `INIT.md`, `ROSTER-LIST.md`, `ROSTER-ADD.md`, `ROSTER-EDIT.md`, `ROSTER-FORMAT.md` | Inventaires et aperçus explicites ; leurs contrats ne sont pas remplacés par le format d'implémentation |
| Tests préexistants | `doctor.py:self_test`, `roster.py:self_test`, `check_roster.py`, `check_links.py`, `check_links2.py` | Auto-tests et vérification de liens ; aucun scénario de volume avant ce changement |

## Portée de la preuve

`test_luucycle_invocation_contract.py` contrôle statiquement les instructions de
routage, d'approbation et de revue dans `RULES.md` et `IMPLEMENT.md` :
Focused et Extended, tous deux avec builder puis verifier indépendant, même pour
petit code ou documentation ; diff complet, tests pertinents, contextes neufs et
même Agent ID/CLI autorisé au meilleur fit. Il couvre les risques proches et
exigences utilisateur/projet/skill de revue approfondie imposant Extended, UI Gate, réapprobation après
hausse de risque, acceptation incomplète sans revue, bilan réel et absence de
récursion pour Audit/Doctor/read-only. Ces assertions de texte ne classent pas des
demandes et ne simulent ni ne prouvent la conduite d'un agent ; aucun gain de performance
n'est établi. Pour cette politique :
`agent behavior: NOT_EVALUATED` ; les observations natives datées ci-dessous
portent sur leurs propres scénarios, pas sur cette politique.

Le contrat est défini dans [COMPACT.md](../skills/luucycle/COMPACT.md). Les tests
prouvent sa projection, sa conservation des champs déclarés critiques et ses
arrêts sur les fixtures. Ils ne peuvent pas découvrir une information critique
qu'un producteur aurait cachée dans `detail`, vérifier la vérité d'un rapport,
ni remplacer l'approbation et la validation des preuves par le coordinateur.

Les tests `test_compact.py` portent sur la frontière normalisée
`luucycle.return.v1`. Un schéma natif directement présenté au projecteur provoque
STOP. L'adaptateur distinct `orca_adapter.py` est testé par
`test_orca_adapter.py` sur des receipts natifs Orca **1.4.229** versionnés avec
provenance. Sa portée est l'inventaire local de workers terminés et libérés ;
versions et hôtes distants supplémentaires restent non pris en charge et provoquent
STOP. `orca_inbox.py` couvre séparément les Deliveries et l'autorité courante locale;
son CLI projette les retours avant stdout. Voir
[ORCA-ADAPTER.md](../skills/luucycle/ORCA-ADAPTER.md).

L'inspection de fixtures conserve `source_verified: false`. La collecte réelle
possède sa propre récupération en lecture seule et requiert un stockage autorisé.
Sans attentes de preuve par tâche, elle renvoie `acceptance: NOT_EVALUATED` : la
présence de vrais records ne vaut pas acceptation du travail des workers.

Deux tests live sont ignorés par défaut. Leur opt-in explicite est
`ORCA_ADAPTER_LIVE_TEST=1` ; ils interrogent le Run existant référencé par les
specimens, avec le runtime correspondant, sans créer de worker ni envoyer de
message. Les tests, même exécutés avec `-B`, créent des fichiers temporaires :
définir `TMPDIR` vers un répertoire scratch autorisé avant exécution. Ils ne
conviennent pas à une tâche qui interdit toute création de fichier.

`test_orca_launch.py` contrôle l'alias Orca séparé de l'ID roster et le preflight
gratuit par agent sélectionné, pas un lancement réel. `test_git_baseline.py`
contrôle la capture/comparaison sans nettoyage des états Git sales, y compris
index, fichiers non suivis et cibles absentes. Voir
[GIT-BASELINE.md](../skills/luucycle/GIT-BASELINE.md) pour les limites et les
changements préexistants protégés.

Le contrôle d'hygiène ci-dessus cible uniquement `skills/luucycle`. Chaque bilan
doit citer le périmètre, le nombre de fichiers et les diagnostics effectivement
retournés ; ne pas confondre ce résultat avec un linter global de bibliothèque.

`test_help_roster_edit_contract.py` vérifie les contrats textuels du README,
de l'aide canonique [HELP.md](../skills/luucycle/HELP.md), de son alias et de
[ROSTER-EDIT.md](../skills/luucycle/ROSTER-EDIT.md). `test_roster_edit.py` exerce
le vrai CLI `roster.py` sur des rosters synthétiques temporaires : plan sans
écriture, mise à jour du même ID, conservation des pairs/rôles/états désactivés,
readback exact et refus des bases ou aperçus modifiés. Le script commun reste un
upsert générique : le périmètre « existants seulement », l'approbation humaine et
le consentement frais aux probes sont des instructions de branche, pas des
contrôles exécutables. Ces tests ne valident ni une réévaluation agent réelle,
ni les catalogues, prix ou quotas actuels des fournisseurs.

`test_worker_contract.py` contrôle le constructeur de prompt, les preuves présentes
dans le payload natif, les identités attribuées au lancement et le chemin d'envoi
contrôlé. `test_orca_inbox.py` couvre les questions, les settlements avant libération,
les preuves manquantes, les sources incohérentes et la projection avant stdout.
Les specimens `fixtures/orca/delivery-1.4.229/` sont des réponses natives exactes
du cycle ci-dessous avec empreintes et provenance; leur lecture hors ligne reste
`source_verified: false` et n'appelle aucun modèle.

## Cycle réel local — 25 octobre 2026

Run `run_1ca5b4d322df`, Orca 1.4.229, dépôt jetable contenant avant exécution un
index staged, des changements unstaged, un fichier non suivi et un fichier ignoré.
Le test a construit un utilitaire UTF-8 puis révisé intentionnellement son contrat
pour exercer une reprise dans un terminal neuf. Ce scénario reste distinct d'une
détection automatique de défaut ou d'un fallback.

| Tâche | Modèle effectif | Résultat |
| --- | --- | --- |
| Builder initial | Gemini 3.8 Flash High, alias `antigravity` | 2 tests verts, receipt validé |
| Reprise TDD, terminal neuf | Codex `gpt-5.6-luna`, effort `high` | 3 tests verts, receipt validé |
| Verifier indépendant, terminal neuf | Codex `gpt-5.6-luna`, effort `high` | 3 tests verts, aucune écriture |

Les préférences natives demandées/effectives ont été comparées. Les trois
Dispatchs ont été libérés puis leurs Deliveries acquittées. Les attestations du
skill chargé étaient présentes dans `payload.task_evidence`; les chemins et
empreintes ont été vérifiés, sans assimiler une déclaration à une preuve de lecture
interne. La comparaison baseline a conservé HEAD, index et chaque contenu initial;
les seuls deltas autorisés concernaient les deux nouveaux fichiers de la fixture.

Le chemin contrôlé a enqueued un message pendant le travail du builder après
lecture fraîche d'autorité. Après settlement et libération, il a refusé une autre
tentative avec `sent: false` et aucun appel send. Cette observation vérifie ce chemin
local; la paire read/send reste non atomique et les clients directs restent hors
de son périmètre.

Mesure mécanique sur les mêmes sources retenues et une projection conservant les
contrôles de collection et de lifecycle, en octets JSON UTF-8 :

| Tâche | Captures natives complètes | Enveloppe normalisée | Projection | Réduction normalisée |
| --- | ---: | ---: | ---: | ---: |
| Builder | 70 282 | 33 204 | 21 808 | 34,32 % |
| Reprise | 87 974 | 40 806 | 23 945 | 41,32 % |
| Verifier | 106 965 | 50 010 | 26 814 | 46,38 % |

Les captures natives comprennent le guide et les lectures d'autorité répétées;
leur comparaison avec la projection donne 68,97 à 74,93 %, avec un périmètre différent
de la réduction normalisée. Ces chiffres ne mesurent pas les tokens ni le contexte
total. L'objectif de moins de 2 000 tokens par tour demeure non démontré. La pagination
de l'inventaire historique est testée hors ligne; l'inbox exige actuellement une
page d'autorité complète. Fallback, remote et CAS atomique ne sont pas validés par ce cycle.

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
