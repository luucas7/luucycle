# Recherche : une amélioration vérifiable de luucycle

Consultation : 2026-10-26. Rédaction : 2026-10-26.

## Décision et portée

Retenir une boucle empirique, obligatoire pour chaque lot mais proportionnée :
baseline → recherche ciblée → hypothèse réfutable → changement minimal → validation
→ revue indépendante contradictoire → résolution → bilan avant/après.
Ce choix est une politique de maintenance adaptée au dépôt, **pas LA meilleure
méthode universelle**, ni une amélioration comportementale déjà démontrée.
La [procédure](skill-improvement.md) est l'autorité opérationnelle ; ce rapport
explique ses choix et garde leurs limites, sans dupliquer les règles du skill.

Luucycle est surtout une préférence d'orchestration encodée : plan approuvé,
routage vers les skills propriétaires, roster et rôles distincts, workers one-shot,
retours compacts, preuves et arrêts. L'enjeu prioritaire est la fidélité aux
frontières, pas simplement le nombre de tâches terminées. La distinction
« capability uplift » / « encoded preference » d'Anthropic soutient des objectifs
d'eval différents, notamment fidélité du workflow et réévaluation à changement
de modèle.[3]

## Recherche réellement réalisée

Recherche web de méthodes d'évaluation, puis récupération **HTTP complète** de neuf
sources primaires : deux fournisseurs de modèles, une spécification, un retour
expérimental de fournisseur d'outils et quatre articles originaux. `web_extract`
a échoué car le backend configuré est search-only ; récupération alternative par
`requests`, extraction du texte par BeautifulSoup après retrait de scripts/styles
et navigation. Aucun paramètre du runtime n'a été changé. Les snippets ont servi à
la découverte, pas à la justification des conclusions.

Les corps extraits ont été lus sur les méthodes, résultats, limites et conclusions
utiles ; les parties non pertinentes des longues annexes n'ont pas toutes été lues.
Les liens arXiv non versionnés ont résolu vers les versions suivantes dans le HTML
récupéré : `2602.11988v3`, `2601.20404v2`, `2602.12670v4`, `2607.22520v1`.
Les résultats ci-dessous concernent ces versions, pas des résumés anciens de v1.
Les pages web sont évolutives ; la date est une date de consultation, pas une
prétendue date de publication commune. L'article skill-creator déclare une
publication le 2026-03-03 dans ses métadonnées HTML.[3]

## Comparaison des approches

### Fournisseurs : recommandations utiles, non essais universels

**OpenAI** définit l'eval comme prompt → run capturé (trace et artefacts) → contrôles
→ score comparable. Il recommande de fixer le succès avant d'écrire le skill,
distinguer résultat/processus/style/efficacité, commencer par des graders
déterministes et étendre les contrôles selon le risque. Son exemple 10–20 prompts
est un point de départ proposé, pas un nombre de répétitions statistiquement
validé pour luucycle.[1]

**Anthropic — bonnes pratiques** recommande concision, dévoilement progressif,
évaluations avant raffinement, tâches réelles et séparation entre un auteur
« Claude A » et un utilisateur « Claude B » dans une instance fraîche. C'est une
méthode de conception fournisseur, pas une garantie d'indépendance du jugement ni
une preuve que « MUST » améliore tout modèle.[2]

**Anthropic — skill-creator** ajoute contextes indépendants, benchmarks temps/tokens
et comparateurs A/B ignorant l'identité des variantes. L'article annonce une
amélioration du déclenchement sur cinq de ses six skills documentaires publics ;
cette observation de produit ne quantifie pas notre routage ou notre sécurité.[3]

**Agent Skills** spécifie `name`/`description`, références et chargement progressif.
La recommandation d'un `SKILL.md` court et de références ciblées soutient le choix
d'un pointeur racine court ; le respect d'un format n'est pas une mesure de
conformité comportementale.[6]

### Résultats contradictoires et non interchangeables

| Source lue | Résultat rapporté | Limite importante pour ce dépôt |
| --- | --- | --- |
| Evaluating AGENTS.md, v3 | Pas d'amélioration générale significative du succès ; coût d'inférence accru de plus de 20 % en moyenne ; les aperçus de repo ne sont pas utiles dans l'étude.[4] | Tâches de résolution Python, pas notre coordination multi-agent. Effets marginaux négatifs des fichiers générés et positifs des fichiers développeurs **non significatifs** : ne pas reprendre l'affirmation ancienne « AGENTS.md diminue systématiquement la réussite ».[4] |
| On the Impact of AGENTS.md, v2 | 124 PR sur dix repos ; médiane du temps réduite de 28,64 % et tokens de sortie de 16,58 %.[5] | Évaluation de correction sémantique/fonctionnelle complète explicitement hors périmètre ; sanity check manuel sur 50 tâches. Vitesse ne signifie pas exactitude.[5] |
| SkillsBench, v4 | 87 tâches, huit domaines, 18 configurations ; pass rate moyen 33,9 % → 50,5 %, soit +16,6 points ; forte hétérogénéité.[7] | Skills curatés et vérificateurs déterministes ; les tâches sans séparation mesurable entre conditions sont écartées. Les auteurs qualifient le benchmark de scénario optimiste, non représentatif de tout l'écosystème. Terminal/conteneur, transfert vers GUI et orchestration multi-agent non établi ; contrôles strictement appariés en longueur encore à améliorer.[7] |
| The Regression Tax, v1 | 5 832 exécutions tâche-condition ; 553 transitions de gain contre 324 de régression, compensant 59 % des gains bruts **au grader brut**.[9] | Transitions, **pas 553 tâches distinctes** ; chaque condition n'est exécutée qu'une fois par tâche, sans estimation de variance inter-runs. Le résultat principal conserve un artefact du grader de formules ; les auteurs publient aussi une réévaluation corrigée. Les 59 % ne mesurent donc pas une régression fonctionnelle corrigée. Bureautique, modèle et harness couplés, codage des mécanismes par un auteur ; causalité encore à tester.[9] |
| LangChain, retour de ses propres essais | 82 % avec skills contre 9 % sans dans ses tâches ; formulation positive/négative et Markdown/XML ont des performances similaires dans ses essais de gros skills.[8] | Résultat spécialisé à leurs tâches/outils, pas essai indépendant de notre repo ; ni ces taux, ni le nombre de skills « idéal » observé ne se transfèrent automatiquement.[8] |

Ces résultats ne s'annulent pas : ils portent sur des contenus, tâches, graders,
configurations et métriques différents. Ils justifient de **mesurer localement**,
plutôt que choisir le résultat qui confirme une intuition. L'étude AGENTS.md v3
met notamment en garde contre l'exploration et les tests supplémentaires qui
augmentent le coût sans succès significativement meilleur.[4] SkillsBench apporte
l'objection positive : des procédures curatées peuvent fortement aider dans une
comparaison appariée, sans valider toute instruction ajoutée.[7]

Le guide local `writing-for-agents` fournit des heuristiques utiles : pointeurs
explicites, critère de fin vérifiable, co-localisation, source de vérité unique et
pruning. Sa préférence pour les formulations positives sera utilisée comme
heuristique de rédaction, non comme loi empirique : LangChain rapporte justement
peu de différence entre formulations positives et négatives dans son contexte.[8]

### Arbitrage retenu

| Option | Décision locale | Pourquoi |
| --- | --- | --- |
| Audit exhaustif et recherche générale avant chaque micro-édition | Écarter | Coût et récursion sans proportion au risque ; la source externe pertinente peut être réutilisée avec date et justification. |
| Long AGENTS.md avec résumé intégral de l'architecture | Écarter | Réplique des informations consultables ; coût permanent de contexte et bénéfice non démontré.[4] |
| Contrats de texte seuls | Garder comme filet rapide, insuffisant | Liens et obligations documentés sont vérifiables ; ils ne révèlent ni activation ni comportement agent.[1] |
| Tests de scripts + contrôles négatifs + traces | Base de validation | Signal déterministe et explicable sur les entrées testées ; à distinguer d'un vrai run agent.[1] |
| Auteur unique évaluant ses propres formulations | Écarter comme gate final | Une instance fraîche et une comparaison masquée peuvent réduire la contamination, sans annuler les biais.[2][3] |
| Optimisation automatique live de chaque patch | Différer | Besoin de budget, autorisations, isolement, graders calibrés et preuves natives ; aucun de ces coûts n'est autorisé par une simple procédure. |
| Boucle ciblée et reviewer qui cherche un contre-exemple | Retenir | Rend les hypothèses et limites contestables ; décompte gains/régressions plutôt qu'une moyenne seule.[9] |

## Inspection du dépôt et preuves locales

État de départ transmis et vérifié pour HEAD :
`600aa341a89ce2e9ad55c8d3e90ce3d6c7acf93e`, branche principale au départ propre.
Des modifications d'autres agents sont prévues en parallèle ; aucune conclusion
avant/après ne doit attribuer leur effet à cette documentation.

Lecture de `SKILL.md`, `RULES.md`, `IMPLEMENT.md`, `tests/README.md`,
`tests/test_luucycle_invocation_contract.py`, `tests/test_hardening_contract.py`,
`tests/test_behavioral_trace.py`, des portions du collecteur et des tests du contrat
worker ; les deux documents locaux `writing-for-agents` et `SKILL-MECHANICS` ont
été lus intégralement. Leurs fichiers restent inchangés par cette mission.

### Baseline prédiff et exécutions réellement observées

- **Baseline globale prédiff exécutée par le coordinateur**, transmise avec sa
  provenance le 2026-10-26 : `python3 -B -m unittest discover -s tests -v` →
  `Ran 223 tests in 9.680s`, `OK (skipped=2)` : 221 réussites, deux skips live.
  Ce résultat n'est pas présenté comme une deuxième exécution de ce sous-agent.
- **Sous-suite comportementale exécutée ici**, avant création des documents :
  `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p test_behavioral_trace.py -v`
  → `Ran 20 tests in 0.182s`, `OK`.
- **Contrats nouveaux, phase rouge réelle** : six méthodes, sept échecs d'assertion
  en comptant les sous-cas, parce que les trois documents attendus sont absents ;
  le contrôle négatif du vérificateur de liens passe. Un premier essai levait des
  `FileNotFoundError` ; le diagnostic a été corrigé en assertion explicite avant
  cette phase rouge, plutôt que présenter une erreur technique comme un test utile.

Les tests comportementaux existants utilisent `MockOrchestratorRunner` et des
fixtures synthétiques. Leur nom ne les transforme pas en observation d'un modèle.
Le dossier `tests/README.md` décrit des observations natives antérieures et leurs
limites ; elles ne sont **pas réexécutées** ici. L'attestation d'un skill dans un
receipt n'établit pas que le modèle a porté attention à ses règles.

### Probe déterministe qui contredit une conclusion trop forte

Exécution locale du vrai collecteur/test harness du dépôt, **aucun modèle live** :

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import json,sys; sys.path.insert(0,"tests"); from behavioral_trace import TraceCollector,MockOrchestratorRunner; cases={"empty":TraceCollector(),"nominal":MockOrchestratorRunner().run_nominal_scenario(),"unjustified_detail":MockOrchestratorRunner().run_verbose_scenario(inspect_detail=True),"rejected_post_settlement_attempt":MockOrchestratorRunner().run_post_completion_input_scenario()[0]}; print(json.dumps({name:{"events":len(trace),"violations":[v.invariant_name for v in trace.verify_all_invariants()],"rejected_events":sum(bool(e.metadata.get("rejected")) for e in trace)} for name,trace in cases.items()},indent=2))'
```

| Entrée réellement exécutée | Événements | Violations retournées | Tentatives rejetées |
| --- | ---: | --- | ---: |
| Vide | 0 | Aucune | 0 |
| Nominale synthétique | 3 | Aucune | 0 |
| Lecture détail injustifiée injectée | 4 | `projection_boundary_respect` | 0 |
| Tentative post-settlement rejetée | 4 | `zero_post_settlement_prompts` | 1 |

L'absence de violation sur la trace vide est une propriété logique du checker,
pas nécessairement un bug : il ne peut examiner que les événements fournis. Elle
**réfute** toutefois « zéro violation implique workflow réellement exécuté ».
Le cas rejeté prouve aussi que le compteur d'invariant voit une **tentative** : il
ne prouve pas un envoi externe effectif. Ces observations justifient de reporter
couverture, tentatives et effets séparément. Aucun chiffre ici ne mesure
l'amélioration d'un agent après lecture de notre procédure.

## Priorités concrètes, sans les implémenter hors périmètre

1. **P0 — Évaluer les frontières, pas les seules sorties.** Préparer des cas de
   routage explicite et voisin négatif, plan non approuvé, lecture seule,
   terminal déjà settled, preuve partielle et baseline sale. Se servir des tests
   existants comme oracle de code, pas comme preuve de comportement d'un LLM.
2. **P0 — Ajouter un contrôle de couverture à l'eval future.** Une trace native
   doit contenir les événements requis pour le cas ; distinguer tentative refusée,
   action envoyée et garantie runtime. Garder le cas vide comme contrôle négatif
   du protocole, sans changer aujourd'hui le sens du checker existant.
3. **P1 — Capturer un petit corpus apparié autorisé.** Baseline actuelle vs patch,
   mêmes modèles/harness/permissions ; conserver gains et régressions, traces et
   erreurs d'infrastructure. Le corpus inclut des cas réservés ; ne pas optimiser
   la formulation uniquement sur les cas déjà vus. La taille dépendra du coût et
   de la variabilité, pas d'une constante « scientifique » empruntée à un blog.
4. **P1 — Vérifier pointeurs et source de vérité.** Le routeur possède déjà des
   branches séparées. Retirer les doublons seulement si le chargement et les
   frontières restent corrects ; comparer contenu retiré, maintien du contrat et
   coût réel plutôt que nombre de lignes seul.
5. **P2 — Tester la portabilité et le gain de contexte.** L'adaptateur possède un
   périmètre Orca versionné ; les fixtures et observations historiques ne
   couvrent pas tous runtimes, remote, fallback ou verrou atomique. Les réductions
   d'octets publiées dans le guide de tests ne sont ni des tokens ni une mesure de
   contexte total. Une future intégration requiert autorisation et budget distincts.

## Hypothèse, bilan et inconnus de ce lot

Hypothèse documentaire : un pointeur racine court, une procédure à gates
vérifiables et des contrats de liens/matrice rendent la politique accessible et
cohérente sans gonfler le routeur du skill. Rejet si pointeur absent, liens cassés,
un profil de changement peut contourner une gate, ou la documentation assimile
un test statique à une preuve agent. La conformité réelle demeure
`agent behavior: NOT_EVALUATED` jusqu'à des evals autorisées.

La mission de recherche initiale portait sur `AGENTS.md`, `docs/` et
`tests/test_repository_workflow.py`. Le lot comprend aussi les changements
README/help/roster réalisés en parallèle et leurs corrections de revue.
Aucun commit/push, modèle live, probe facturé ou mutation de service externe
n'a été effectué.
Les contrats testent le graphe documentaire, les profils et leurs gates ordonnées,
la cohérence des références et les contrôles négatifs des liens, pas des centaines
de formulations figées. Ces tests ne vérifient pas automatiquement l'obéissance
sémantique de toutes les phrases de la procédure.

**Autorisation racine :** le premier refus natif d'écrire `AGENTS.md` n'a pas été
contourné. Le coordinateur a demandé puis obtenu l'accord explicite de l'utilisateur
avant de créer le pointeur. Les deux contrats alors rouges sont ensuite passés.

**Revue contradictoire indépendante**, le 2026-10-26 :

- `sa-0-80983058` a examiné les 19 fichiers du diff initial et reproduit deux
  défauts : liens vers une dépendance locale ignorée, et règle globale incompatible
  avec le bootstrap. Les corrections ajoutent une lecture amont épinglée avec
  empreintes, un test d'export sans dépendances locales et l'exception explicite
  de création initiale déjà possédée par `ROSTER-ADD.md`.
- `sa-0-b0448daf` a vérifié les neuf sources via HTTP. Aucun chiffre erroné ;
  deux limites manquantes ont été ajoutées : sélection optimiste de SkillsBench,
  résultats au grader brut et absence de répétitions de Regression Tax. Le
  coordinateur a relu ces passages amont ; les URL arXiv sont désormais versionnées.
- `sa-0-b814c37d` a revérifié les quatre corrections, relu les sources amont et
  rejoué les contrats ciblés dans le checkout et un export sans dépendances
  locales : quatre corrections acceptées, aucun défaut résiduel dans ce périmètre.
  Le coordinateur a comparé les empreintes des cinq fichiers à celles du reviewer
  avant d'ajouter ce bilan final ; elles correspondaient toutes.

**Contrôles réellement réexécutés par le coordinateur après ces corrections :**

- `python3 -B -m unittest discover -s tests -q` dans le checkout :
  `Ran 243 tests in 10.786s`, `OK (skipped=2)`.
- Même commande sur un export de **97 fichiers** suivis et nouveaux non ignorés,
  sans `.git`, `.agents`, `.claude` ni registre local :
  `Ran 243 tests in 10.995s`, `OK (skipped=2)`.
- Dans cet export, `check_skill_hygiene.py skills/luucycle` : 18 fichiers,
  zéro violation. Le `check_links.py` préexistant utilise un chemin absolu vers
  le checkout initial : son succès ne prouve pas les liens de l'export. Les tests
  portables `local_link_errors` ont vérifié les fichiers et ancres documentaires
  sur l'export. Self-tests Doctor, roster et check_roster passés précédemment,
  scripts inchangés depuis.
- Les deux lectures amont de `writing-for-agents` sont accessibles par HTTP ;
  leurs SHA-256 correspondent aux empreintes de la procédure. Aucun vendor
  ni installation implicite. `git diff --check` réussit.

Les variables `PYTHONDONTWRITEBYTECODE=1`, `ORCA_ADAPTER_LIVE_TEST=0` et le
`TMPDIR` scratch autorisé sont conservés. Cela représente 241 réussites et
deux tests live ignorés, contre 221 réussites et deux skips dans la baseline.
L'export sert aussi de test de portabilité ; il ne simule pas un run de modèle.
La revérification indépendante des corrections est terminée. Décision : livré au
niveau documentaire et programme hors ligne démontré ; conduite agent live
non évaluée. Aucune de ces observations ne démontre une amélioration comportementale
d'un agent après lecture de la procédure.

### Frontière de distribution

La politique racine s'applique à la maintenance de ce dépôt, pas aux projets
consommateurs. Le coordinateur a vérifié le 2026-10-26 la source première partie
`https://raw.githubusercontent.com/vercel-labs/skills/main/src/installer.ts` :
`installSkill` appelle `copyDirectory(skill.path, ...)` pour les copies et la
copie canonique des installations symlink. Une installation depuis ce dépôt
distribue donc `skills/luucycle/` et ses nouvelles branches, pas l'AGENTS.md ou
les documents `docs/` situés hors de ce dossier. Les changements locaux doivent
être publiés explicitement avant d'être récupérables depuis GitHub ; aucun push
n'est effectué dans ce lot.

## Sources

[1] https://developers.openai.com/blog/eval-skills — Testing Agent Skills Systematically with Evals | OpenAI Developers
[2] https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices — Skill authoring best practices - Claude Platform Docs
[3] https://claude.com/resources/articles/improving-skill-creator-test-measure-and-refine-agent-skills — Improving skill-creator: Test, measure, and refine Agent Skills | Claude by Anthropic
[4] https://arxiv.org/html/2602.11988v3 — Evaluating AGENTS.md:Are Repository-Level Context Files Helpful for Coding Agents?
[5] https://arxiv.org/html/2601.20404v2 — On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents
[6] https://agentskills.io/specification — Specification - Agent Skills
[7] https://arxiv.org/html/2602.12670v4 — SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks
[8] https://www.langchain.com/blog/evaluating-skills — Evaluating Skills
[9] https://arxiv.org/html/2607.22520v1 — The Regression Tax: Decomposing Why Skills Help — and Hurt — LLM Agents
