# Changelog

## [0.6.1](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.6.0...v0.6.1) (2026-03-13)

### Bug Fixes

* **533:** add missing note field for modules ([1524eac](https://github.com/EPFL-ENAC/co2-calculator/commit/1524eac4676a0e5e1e9ea05e41d8fe3cdf76fae7))
* **533:** correct validation for buildings & process_emissions ([3ad0486](https://github.com/EPFL-ENAC/co2-calculator/commit/3ad0486801f10d5285848198eb5e182d67435116))
* **headcount:** add rule for fte > 1 not possible ([635be85](https://github.com/EPFL-ENAC/co2-calculator/commit/635be85f5fec405457756a8eb5db99abff9df65c))
* **frontend-csv:** add 30 second timeout for csv fail ([35cc8e3](https://github.com/EPFL-ENAC/co2-calculator/commit/35cc8e399547f6ece9437023f590abcb1eeb5d93))
* **template:** refactor template handling and update Cécile's name in headcount content ([d992dab](https://github.com/EPFL-ENAC/co2-calculator/commit/d992dabf812a20a0a97e34cc664a9e633815284c))
* **template:** update headcount template mapping and restore missing modules ([80c2bd3](https://github.com/EPFL-ENAC/co2-calculator/commit/80c2bd3e810e14496539de4d47572c4321f31ff9))
* **template-rows:** update professional travel train content to reflect correct destination ([a757a4e](https://github.com/EPFL-ENAC/co2-calculator/commit/a757a4e7ccddef0bfbe7785501bd62a405bad643))

### Features

* **templates:** add new CSV templates ([cd10c8a](https://github.com/EPFL-ENAC/co2-calculator/commit/cd10c8a2784eee402b7ebc4222e0258bd25cc46d))

---

## [0.6.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.5.0...v0.6.0) (2026-03-04) — Sprint 6

### Features

* **process-emissions:** add new Process Emissions module for lab process emissions calculation ([#493](https://github.com/EPFL-ENAC/co2-calculator/pull/493), [#497](https://github.com/EPFL-ENAC/co2-calculator/pull/497))
* **buildings:** rename Infrastructure module to Buildings with Archibus room data enrichment ([#524](https://github.com/EPFL-ENAC/co2-calculator/pull/524))
* **purchase:** add purchase module with scientific/IT equipment, consumables, bio products, services, vehicles ([#514](https://github.com/EPFL-ENAC/co2-calculator/pull/514))
* **travel-csv:** add CSV upload support for professional travel (planes and trains) ([#438](https://github.com/EPFL-ENAC/co2-calculator/pull/438), [#516](https://github.com/EPFL-ENAC/co2-calculator/pull/516))
* **travel:** multiply distance by number_of_trips in calculation and UI ([#441](https://github.com/EPFL-ENAC/co2-calculator/pull/441))
* **notes:** add "Add with note" dialog for data entries ([#486](https://github.com/EPFL-ENAC/co2-calculator/pull/486))
* **results:** integrate dynamic emission breakdown API, validation states and chart visibility ([#449](https://github.com/EPFL-ENAC/co2-calculator/pull/449), [#479](https://github.com/EPFL-ENAC/co2-calculator/pull/479), [#490](https://github.com/EPFL-ENAC/co2-calculator/pull/490))
* **results:** add placeholder chart and hide chart bars when no data ([#544](https://github.com/EPFL-ENAC/co2-calculator/pull/544), [#545](https://github.com/EPFL-ENAC/co2-calculator/pull/545))
* **backoffice:** data management tab functional ([#439](https://github.com/EPFL-ENAC/co2-calculator/pull/439))
* **audit:** implement Elasticsearch synchronization for audit logs ([#450](https://github.com/EPFL-ENAC/co2-calculator/pull/450), [#485](https://github.com/EPFL-ENAC/co2-calculator/pull/485))
* **audit:** add pagination, search bar, stat cards and table ([#450](https://github.com/EPFL-ENAC/co2-calculator/pull/450))
* **taxonomy:** add module taxonomy per module in backend and use it in form selects ([#521](https://github.com/EPFL-ENAC/co2-calculator/pull/521))
* **reporting:** implement frontend filter functionality for reporting units ([#520](https://github.com/EPFL-ENAC/co2-calculator/pull/520))
* **stats:** populate stats column on carbon report modules ([#550](https://github.com/EPFL-ENAC/co2-calculator/pull/550))
* **emission-types:** refactor emission types with new breakdown structure ([#525](https://github.com/EPFL-ENAC/co2-calculator/pull/525))
* **seeder:** add async seeder for data entries and emissions using asyncpg ([#519](https://github.com/EPFL-ENAC/co2-calculator/pull/519))
* **helm:** add PodDisruptionBudget, imagePullSecrets to ServiceAccount, Elasticsearch vars and secret ([#445](https://github.com/EPFL-ENAC/co2-calculator/pull/445), [#464](https://github.com/EPFL-ENAC/co2-calculator/pull/464), [#515](https://github.com/EPFL-ENAC/co2-calculator/pull/515))
* **formatting:** standardize number formatting for CO2 emissions and FTE ([#491](https://github.com/EPFL-ENAC/co2-calculator/pull/491))
* **cicd:** add security scan with CodeQL v4 and Dependabot configuration ([#135](https://github.com/EPFL-ENAC/co2-calculator/pull/135), [#546](https://github.com/EPFL-ENAC/co2-calculator/pull/546))

### Bug Fixes

* fix factors used in train trips / cross-border train trips ([#437](https://github.com/EPFL-ENAC/co2-calculator/pull/437))
* disable CSV upload when module is validated ([#443](https://github.com/EPFL-ENAC/co2-calculator/pull/443))
* fix process card appearing twice ([#497](https://github.com/EPFL-ENAC/co2-calculator/pull/497))
* override ajv and minimatch due to security vulnerabilities ([#494](https://github.com/EPFL-ENAC/co2-calculator/pull/494))
* fix module table styling, process emissions data, and store cache invalidation ([#505](https://github.com/EPFL-ENAC/co2-calculator/pull/505))
* fix headcount emission rows duplication and null kg_co2eq ([#549](https://github.com/EPFL-ENAC/co2-calculator/pull/549))
* fix travel distance calculations for plane and train trips ([#548](https://github.com/EPFL-ENAC/co2-calculator/pull/548))
* fix helm chart securityContext optional ([#474](https://github.com/EPFL-ENAC/co2-calculator/pull/474))
* add postinstall script to prepare Quasar application ([#446](https://github.com/EPFL-ENAC/co2-calculator/pull/446))

### Refactoring & Chore

* refactor professional travel: replace `trips` with separate plane and train submodules ([#516](https://github.com/EPFL-ENAC/co2-calculator/pull/516))
* reorganize code per module ([#517](https://github.com/EPFL-ENAC/co2-calculator/pull/517))
* reduce login SVG size by ~94% ([#552](https://github.com/EPFL-ENAC/co2-calculator/pull/552))
* rollback to uvicorn for OpenTelemetry compatibility ([#481](https://github.com/EPFL-ENAC/co2-calculator/pull/481))
* correct npm ci without postinstall ([#475](https://github.com/EPFL-ENAC/co2-calculator/pull/475))

---

## [0.5.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.4.0...v0.5.0) (2026-03-04)

### What's Changed

* fix(docs): correct broken relative links to prevent strict mode build failures by @BenBotros in [#374](https://github.com/EPFL-ENAC/co2-calculator/pull/374)
* feat(CICD): forward helm version to gitops by @nicdub in [#366](https://github.com/EPFL-ENAC/co2-calculator/pull/366)
* chore: remove dead resource example by @guilbep in [#377](https://github.com/EPFL-ENAC/co2-calculator/pull/377)
* Refactor/consolidate user unit by @guilbep in [#379](https://github.com/EPFL-ENAC/co2-calculator/pull/379)
* feat: update color scheme by @BenBotros in [#378](https://github.com/EPFL-ENAC/co2-calculator/pull/378)
* chore(manage_db): make helper script better at handling kube instances by @guilbep in [#382](https://github.com/EPFL-ENAC/co2-calculator/pull/382)
* Chore/216 rename inventory to carbon report by @guilbep in [#383](https://github.com/EPFL-ENAC/co2-calculator/pull/383)
* feat/237 right chart by @BenBotros in [#381](https://github.com/EPFL-ENAC/co2-calculator/pull/381)
* Chore/216 backend new model by @guilbep in [#387](https://github.com/EPFL-ENAC/co2-calculator/pull/387)
* feat(OTel): add OpenTelemetry by @nicdub in [#389](https://github.com/EPFL-ENAC/co2-calculator/pull/389)
* fix(OTel): launch OTel by default+add collector conf by @nicdub in [#391](https://github.com/EPFL-ENAC/co2-calculator/pull/391)
* feat/331 improve destination search by @BenBotros in [#388](https://github.com/EPFL-ENAC/co2-calculator/pull/388)
* Update documentation editing texts by @charlottegiseleweil in [#394](https://github.com/EPFL-ENAC/co2-calculator/pull/394)
* test - Update my_lab.ts by @tmkmrnk in [#396](https://github.com/EPFL-ENAC/co2-calculator/pull/396)
* Update Guidance term common.ts by @maidinh-metier in [#395](https://github.com/EPFL-ENAC/co2-calculator/pull/395)
* Update equipment_electric_consumption.ts by @Anna-Kounina-Masse in [#397](https://github.com/EPFL-ENAC/co2-calculator/pull/397)
* Migrate equipment to data entry by @guilbep in [#390](https://github.com/EPFL-ENAC/co2-calculator/pull/390)
* Update professional_travel.ts by @Anna-Kounina-Masse in [#407](https://github.com/EPFL-ENAC/co2-calculator/pull/407)
* Feat/external cloud and ais by @guilbep in [#409](https://github.com/EPFL-ENAC/co2-calculator/pull/409)
* text: Update descriptions for Professional Travel module by @ambroise-dly in [#408](https://github.com/EPFL-ENAC/co2-calculator/pull/408)
* text: change text of Doc by @ambroise-dly in [#393](https://github.com/EPFL-ENAC/co2-calculator/pull/393)
* fix(db-drop): set drop db with force by @nicdub in [#411](https://github.com/EPFL-ENAC/co2-calculator/pull/411)
* feat: add CSV data import with real-time job status updates by @guilbep in [#412](https://github.com/EPFL-ENAC/co2-calculator/pull/412)
* fix(external-cloud): correct default for external-cloud by @guilbep in [#420](https://github.com/EPFL-ENAC/co2-calculator/pull/420)
* feat(helm): add OTel metadata by @nicdub in [#418](https://github.com/EPFL-ENAC/co2-calculator/pull/418)
* release v0.5.0 by @guilbep in [#553](https://github.com/EPFL-ENAC/co2-calculator/pull/553)

### New Contributors

* @tmkmrnk made their first contribution in [#396](https://github.com/EPFL-ENAC/co2-calculator/pull/396)
* @maidinh-metier made their first contribution in [#395](https://github.com/EPFL-ENAC/co2-calculator/pull/395)
* @Anna-Kounina-Masse made their first contribution in [#397](https://github.com/EPFL-ENAC/co2-calculator/pull/397)

**Full Changelog**: https://github.com/EPFL-ENAC/co2-calculator/compare/v0.4.0...v0.5.0

---

## [0.4.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.3.0...v0.4.0) (2026-02-10)

### Features

* adapt permission for documentation button ([5260fc8](https://github.com/EPFL-ENAC/co2-calculator/commit/5260fc8b2d8a0b2223806128af66a75e6264651c))
* add all links in homepage ([cf1970f](https://github.com/EPFL-ENAC/co2-calculator/commit/cf1970f8e382e53f7668b833917bac91a9bda1e7))
* add link and change texts ([9b0fe0b](https://github.com/EPFL-ENAC/co2-calculator/commit/9b0fe0b5732f8b44b8e0e63f0cd1f88633fdc154))
* add link to all documentation, add link in a text, change the documentation button per role ([51ab6ef](https://github.com/EPFL-ENAC/co2-calculator/commit/51ab6efb18aa53e4d7823100406df16b1e508618))
* add permissions for all modules and update role definitions ([2932cb2](https://github.com/EPFL-ENAC/co2-calculator/commit/2932cb2cc5d8b6efa1edb9ff73465251067e3fb6))
* add Storybook configuration and dependencies ([cea15e5](https://github.com/EPFL-ENAC/co2-calculator/commit/cea15e5288b54ac257b5d22dbf5be100b80cb568))
* add tonnes CO2-eq to module totals and update display ([f40b414](https://github.com/EPFL-ENAC/co2-calculator/commit/f40b414d8e41185fb4c6747af76f17e761ba5eed))
* added csv file upload dialog ([2b46f06](https://github.com/EPFL-ENAC/co2-calculator/commit/2b46f06fe84b9a845d81f6be92dd5d5898eabf2e))
* added files endpoint with local/s3 and encryption ([#330](https://github.com/EPFL-ENAC/co2-calculator/issues/330)) ([08b7b90](https://github.com/EPFL-ENAC/co2-calculator/commit/08b7b90b9255fd6e6f2ef6407fcd411c5e963bbb))
* added files related env variables to helm chart ([ab24994](https://github.com/EPFL-ENAC/co2-calculator/commit/ab249947f76c21c1a7294f5021b6a3e755fe113d))
* added files store persistence for tracking uploaded temp files ([0fc40d9](https://github.com/EPFL-ENAC/co2-calculator/commit/0fc40d9473dc7cca16d67210e8f8815d141814b5))
* added s3 files store support, delegate file name/path sanitization to enacit4r files lib ([31b4778](https://github.com/EPFL-ENAC/co2-calculator/commit/31b4778485109e73d4bb2bdb710bfedf2a3d6a63))
* added temp file upload dialog ([9b72235](https://github.com/EPFL-ENAC/co2-calculator/commit/9b72235f443e53f004c04d7c0727737ac59daf4b))
* **api-travel:** pass type-check and model migration ([9d8cc59](https://github.com/EPFL-ENAC/co2-calculator/commit/9d8cc59d7aeb9d6dee53428556062eb49601a6ca))
* **auth:** add permissions field to user model ([07eaa45](https://github.com/EPFL-ENAC/co2-calculator/commit/07eaa451eb601f362b35e1d0c9a5bf854812eb08))
* **auth:** allow standard users to edit/delete their own travel records ([a117f96](https://github.com/EPFL-ENAC/co2-calculator/commit/a117f961f2cee74b5ae0f3b1bc8ccdedfb9c6f52))
* **auth:** implement permission calculation system ([5d73b83](https://github.com/EPFL-ENAC/co2-calculator/commit/5d73b83946f41e3f103e61c30e6b3b27b97259e8))
* **auth:** implement permission-based exception handlers and custom errors ([5513d7b](https://github.com/EPFL-ENAC/co2-calculator/commit/5513d7b2d358fd5b4802a7c2de57e9ea8109c8a1))
* **backend:** add permission-based authorization with policy evaluation ([a99145f](https://github.com/EPFL-ENAC/co2-calculator/commit/a99145f4945f2fa077ebf4372095d66ebc804ef8))
* **backend:** support filtered queries and ensure fresh user data ([dd6e268](https://github.com/EPFL-ENAC/co2-calculator/commit/dd6e26888ee1d4378ebbc71aebd1aee1cc404374))
* **backoffice:** add user management endpoints with policy-based access control ([bef8e19](https://github.com/EPFL-ENAC/co2-calculator/commit/bef8e19abd1aaedf4260957d97b94c4b059207ca))
* **charts:** add static evolution over time chart ([33be317](https://github.com/EPFL-ENAC/co2-calculator/commit/33be3173f3f6a92f5a71c46f5623a36cb4c0886d))
* create travel API for Tree chart ([0a514f7](https://github.com/EPFL-ENAC/co2-calculator/commit/0a514f77192e79867de6f576c1c27b8e60513ed1))
* **css:** implement custom link component and design tokens ([b6bec79](https://github.com/EPFL-ENAC/co2-calculator/commit/b6bec795d6910b3cb337ec7f43e8888615e24907))
* document design token & button ([3cb67e3](https://github.com/EPFL-ENAC/co2-calculator/commit/3cb67e35d6ef4e98fb7c1171e7ec8d5dc5683452))
* enforce edit permissions for module data entry ([9832fcb](https://github.com/EPFL-ENAC/co2-calculator/commit/9832fcb146e92bf3cd44579934343dd1b57a3a20))
* **equipment:** add tonnes CO2-eq field to equipment emissions ([9501cbb](https://github.com/EPFL-ENAC/co2-calculator/commit/9501cbba20f99fceecdf412702d361bd8a2f2fb0))
* **erd-generator:** make erd respect linter and keep sorted field to avoid unecessary conflicts ([c872f55](https://github.com/EPFL-ENAC/co2-calculator/commit/c872f5556aeb7b6b3edbee5eac08335700c5af0c))
* **frontend:** add permission guards to backoffice routes ([0e106de](https://github.com/EPFL-ENAC/co2-calculator/commit/0e106de76f2b03f6b72cc370f7d40b6f89d99c2e))
* **frontend:** add permission utility functions and route guard ([ebc2d48](https://github.com/EPFL-ENAC/co2-calculator/commit/ebc2d48db284a22f7d954e2998fa579b8604a537))
* **frontend:** add static TreeMap chart component ([87c8253](https://github.com/EPFL-ENAC/co2-calculator/commit/87c8253e62129dd3e0ae1bc014581a0aef3ae822))
* **frontend:** add TypeScript permissions type definitions ([b0ae205](https://github.com/EPFL-ENAC/co2-calculator/commit/b0ae20595c695b23d97cf2a0dcade38ed8e57ec0))
* **frontend:** implement robust permission error handling ([0b57c49](https://github.com/EPFL-ENAC/co2-calculator/commit/0b57c4965e2f2419427dcaae7c2f5af937cda774))
* give decimal parameter to all module config ([d0d05b8](https://github.com/EPFL-ENAC/co2-calculator/commit/d0d05b8257faab7dc45ac95ad466246fc80fcea4))
* implement localized 403 error handling and page redesign ([cda5993](https://github.com/EPFL-ENAC/co2-calculator/commit/cda5993ae8e1afd409cb165ffe02a28fd03d4ab4))
* implement system permissions and module access control ([684b4bf](https://github.com/EPFL-ENAC/co2-calculator/commit/684b4bf8c44ba123c47a1c15341bffdb45a1db39))
* **module:** restrict date picker navigation to selected year ([e267f04](https://github.com/EPFL-ENAC/co2-calculator/commit/e267f0453c4c58324818ba5a29fc434e2668a22d))
* **modules:** add endpoint to aggregate equipment and travel totals ([45d03a4](https://github.com/EPFL-ENAC/co2-calculator/commit/45d03a456c790588fc8fbfd1cbad132a3006e21e))
* **modules:** add permission-based UI controls for module editing ([c4cd4ef](https://github.com/EPFL-ENAC/co2-calculator/commit/c4cd4ef2ece26696ae8de0ebcd7842ccb77138f4))
* **modules:** implement permission-based access control for headcount ([859b543](https://github.com/EPFL-ENAC/co2-calculator/commit/859b543fc3256052fe700c696918e40e83f9645a))
* **my-lab:** enable sorting and inline editing for student fields ([741fc38](https://github.com/EPFL-ENAC/co2-calculator/commit/741fc3810cdd682f43ef867ac39796ae10ed8c5c))
* refactor module state management and enhance UI components ([8567208](https://github.com/EPFL-ENAC/co2-calculator/commit/8567208a6300ceeb7d338649544450d75237af50))
* remove decimal places from module total result display ([965b265](https://github.com/EPFL-ENAC/co2-calculator/commit/965b265db6e2e5c7492b669345ec5716aa988c45))
* remove smooth curve to Evolution chart ([f23c1ad](https://github.com/EPFL-ENAC/co2-calculator/commit/f23c1adcb5910455534f1ca0411d45a1baff81d0))
* **storybook:** add atom stories ([6839f8f](https://github.com/EPFL-ENAC/co2-calculator/commit/6839f8fa3cc79fe5f7077fdc5bfeb58f3af07d7b))
* **storybook:** add comprehensive Storybook preview configuration ([c52cd6a](https://github.com/EPFL-ENAC/co2-calculator/commit/c52cd6aabc968ccf6e8daf5b467acdf9e09c1bb8))
* **storybook:** add Docker setup to build and serve static Storybook ([7838a6e](https://github.com/EPFL-ENAC/co2-calculator/commit/7838a6e5aba169e7841eb9cc62079d2b55323547))
* **storybook:** add interactive controls to Button stories ([81685fe](https://github.com/EPFL-ENAC/co2-calculator/commit/81685feea1350a150d1062f8a188e7eccb1d498f))
* **storybook:** add layout stories ([de5af3b](https://github.com/EPFL-ENAC/co2-calculator/commit/de5af3b27a70952febef0f31c296c627d3b36630))
* **storybook:** add molecule stories ([81693a1](https://github.com/EPFL-ENAC/co2-calculator/commit/81693a1c8b0ccba0c756f7fad93119502168885e))
* **storybook:** simplify configuration and setup ([5a2890a](https://github.com/EPFL-ENAC/co2-calculator/commit/5a2890af98f5a1b25050d1cbc46d74539def6d6f))
* **travel module:** add travel module ([f2c88c8](https://github.com/EPFL-ENAC/co2-calculator/commit/f2c88c853ce160fe32748a2620b7adb04c2e6cb3))
* **travel:** add validation for identical origin and destination ([7436df2](https://github.com/EPFL-ENAC/co2-calculator/commit/7436df211fd8f2461e1ec7d101042c5ca1417cd2))
* update translations ([4edbe1b](https://github.com/EPFL-ENAC/co2-calculator/commit/4edbe1b3f3898c9a5b9135a3dd4a7f8ac70e81f9))

### Bug Fixes

* add missing fr translation and add missing link to ts ([4758811](https://github.com/EPFL-ENAC/co2-calculator/commit/47588110ed2bf43a01da7004b3ed172723698ec3))
* add missing translation and change the header unit name ([799a2f9](https://github.com/EPFL-ENAC/co2-calculator/commit/799a2f992b849037d70e8d7aba63848540be7b70))
* add ts files in i18n for better categorization ([77f1fec](https://github.com/EPFL-ENAC/co2-calculator/commit/77f1fec6fd249ef0d047e8614c03cee7faeca13b))
* **backend:** correct test for local/ci testing ([af4da29](https://github.com/EPFL-ENAC/co2-calculator/commit/af4da2920aba84e7fc266d46f25843278937f1a4))
* **backend:** remove dead code and not reachable code ([b9e6654](https://github.com/EPFL-ENAC/co2-calculator/commit/b9e6654337f00e895892ef63d8a3759d1b2968be))
* **backend:** sanitize log ([d7e9062](https://github.com/EPFL-ENAC/co2-calculator/commit/d7e9062a13caad431ac783174767660435ae4dbc))
* change CO₂ unit from kg to tonnes in module total result ([1ecc1e7](https://github.com/EPFL-ENAC/co2-calculator/commit/1ecc1e7e3be661f8bfac6ad5fbaf49015879fbad))
* change documentation backoffice name ([89ce293](https://github.com/EPFL-ENAC/co2-calculator/commit/89ce293f76df84fb856e54bd269cfeeb23adad92))
* **charts:** adjust evolution dialog width ([7b6295d](https://github.com/EPFL-ENAC/co2-calculator/commit/7b6295df4033678ac878347ce6b43fca4a16d83e))
* **CICD:** fix deploy task script url ([d42bea9](https://github.com/EPFL-ENAC/co2-calculator/commit/d42bea9adeb7981cd340ecacefcd42c512a4c26f))
* **frontend-i18n:** make format pass ([1cfd7db](https://github.com/EPFL-ENAC/co2-calculator/commit/1cfd7db88b18803feeceeced7a5e4a627d22d471))
* **frontend:** correct code-style ([66a39cf](https://github.com/EPFL-ENAC/co2-calculator/commit/66a39cf8feff42dbd0856e35f0e8da6a2061cc86))
* **frontend:** update eslint and stylelint to ignore build directories ([3337d9a](https://github.com/EPFL-ENAC/co2-calculator/commit/3337d9a0aa94262527b9285b0e6af436ae4860d4))
* **home:** show dash for unstarted modules on homepage ([30bec61](https://github.com/EPFL-ENAC/co2-calculator/commit/30bec6171f8f76f020a65840dcba59167ac9d576))
* **i18n:** use URL encoding for email addresses to prevent vue-i18n parsing errors ([cc36274](https://github.com/EPFL-ENAC/co2-calculator/commit/cc3627400d1c5d4dca8d08d98fefe8a763a01849))
* **prettier:** run prettier on quasar config ([ddb2600](https://github.com/EPFL-ENAC/co2-calculator/commit/ddb2600282b542bbe36b9d4d9b42195851ccf499))
* **professional-travel:** add unit_id validation for travel record creation ([bf569bd](https://github.com/EPFL-ENAC/co2-calculator/commit/bf569bd5507d8c3c37a94612ba1ff02df0df6ca3))
* **professional-travel:** use workspace year when departure date is empty ([6a2e725](https://github.com/EPFL-ENAC/co2-calculator/commit/6a2e7259adb8220cfc0695d1b2b210081cfb3a70))
* **refactor-role:** use enum everywhere ([5392698](https://github.com/EPFL-ENAC/co2-calculator/commit/53926987df3c965dfe00316fcc4c4b66f26f9c2a))
* **storybook:** configure Vue to recognize Quasar custom elements ([c005d96](https://github.com/EPFL-ENAC/co2-calculator/commit/c005d96eeef816bfba9d9b644f57240e2a1b8940))
* **storybook:** fix broken icons ([f5a80dd](https://github.com/EPFL-ENAC/co2-calculator/commit/f5a80dd685c77cf88163a1b969bb753898bb93fe))
* **storybook:** improve configuration and design token alignment ([0b6543b](https://github.com/EPFL-ENAC/co2-calculator/commit/0b6543bccea42a841ddb2318f6a9630879abba90))
* **tests:** replace hard coded role by enum ([400acea](https://github.com/EPFL-ENAC/co2-calculator/commit/400acead88e828ef195d52b5a1f640d2e7fbce15))
* update PR template ([3e4e0ac](https://github.com/EPFL-ENAC/co2-calculator/commit/3e4e0acd66b230e9937ae626d7cc435788fdd527))

---

## [0.3.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.2.0...v0.3.0) (2025-12-23)

### Major Features

**Headcount Module (#75)**
- Implemented complete CRUD operations for personnel management
- Added member and student tracking with FTE calculations
- Created student FTE helper tool for simplified data entry
- Improved role mapping and statistics display
- Enhanced validation and error handling

**Results & Visualization (#213, #236)**
- Added carbon footprint stacked bar charts with standard deviation
- Implemented year-over-year comparison functionality
- Added PNG chart export capability
- Created uncertainty visualization toggles
- Improved number formatting and unit display across all views

**Table Improvements (#228, #235)**
- Refactored pagination, filtering, and search functionality
- Added sticky headers with fixed max height
- Increased table density and optimized column widths
- Implemented better sorting for equipment lists
- Expanded page width from 1200px to 1320px for better data display

### User Experience Enhancements
- Made logo clickable with home page navigation
- Moved timeline from header to module content for better space utilization
- Improved module navigation with prev/next links
- Collapsed modules by default in results view
- Enhanced i18n support with French translations

### Technical Improvements
- Modernized user/unit management architecture
- Added comprehensive test coverage (60% minimum)
- Improved error handling and logging
- Deployed to both enack8s and OpenShift platforms
- Updated documentation structure with user guides

### Bug Fixes
- Corrected equipment sorting and filtering logic
- Fixed unit retrieval and URL parameter handling
- Resolved Safari layout centering issues
- Improved form validation for incomplete entries
- Various tooltip and UI corrections

---

## [0.2.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.1.1...v0.2.0) (2025-12-23)

### Features

* add all roles to login test page [#183](https://github.com/EPFL-ENAC/co2-calculator/issues/183) ([#233](https://github.com/EPFL-ENAC/co2-calculator/issues/233)) ([194b4c1](https://github.com/EPFL-ENAC/co2-calculator/commit/194b4c125dc41e7a8c268dbd287e53be9eed92d0))
* add backoffice button in header ([7b10ebb](https://github.com/EPFL-ENAC/co2-calculator/commit/7b10ebb22f5a385526ee27ac481d7e0632486ed2))
* add distinct test users for each role name, based on User model ([89308ee](https://github.com/EPFL-ENAC/co2-calculator/commit/89308eef9d591acfe5cd0796e8d59d9839429599))
* add epfl favicons ([915935f](https://github.com/EPFL-ENAC/co2-calculator/commit/915935f5d3a8eb9f4254a4635f64b2a9cb4aa4dc))
* add lighthouse-plugin-ecoindex-core dependency ([f9ddaff](https://github.com/EPFL-ENAC/co2-calculator/commit/f9ddaff1a1f50afb278b419dbab3457d32211b1f))
* add unit tests for backoffice API endpoints ([a92bf80](https://github.com/EPFL-ENAC/co2-calculator/commit/a92bf806b435fc69f10219d52fd0c16edd514214))
* **backend:** correct seed with default value ([4141e03](https://github.com/EPFL-ENAC/co2-calculator/commit/4141e03fa4519250f45fd323511a9b65568bf6b6))
* **backoffice:** add backoffice API endpoints and reporting functionality ([31d2970](https://github.com/EPFL-ENAC/co2-calculator/commit/31d2970bca6b9b92fa4e20bca683d2f2eebcc7d5))
* **collapsible:** add collapsible sections ([0e0b82a](https://github.com/EPFL-ENAC/co2-calculator/commit/0e0b82a3070f2cb35fc807675f810db8ee2b55b8))
* **conso-elec-table:** add basic layout/structure for modules and submodules ([97b7991](https://github.com/EPFL-ENAC/co2-calculator/commit/97b799124a947242b7732375ffaad77889d3259b))
* **database:** add PostgreSQL management commands and update foreign key constraints ([b702dae](https://github.com/EPFL-ENAC/co2-calculator/commit/b702dae0f52f2099b86bad81b9ebe65e97fa41eb))
* **delete dialog:** add delete confirmation dialog to ModuleTable ([ce543d1](https://github.com/EPFL-ENAC/co2-calculator/commit/ce543d12158ff1b4265759e0030b7cb337eb0fe1))
* disable access in backoffice navigation for backoffice standard ([f4b4798](https://github.com/EPFL-ENAC/co2-calculator/commit/f4b479864ef040ba2db0844f0808b17e02c2d9b5))
* **documentation-editing:** add documentation editing content ([c631a79](https://github.com/EPFL-ENAC/co2-calculator/commit/c631a794f16e5a365e26f9d16eb11e4d1a7f1c12))
* **equipment:** add class-subclass map endpoint and refactor power ([3e960d2](https://github.com/EPFL-ENAC/co2-calculator/commit/3e960d25f8af5c38b9cc2f843df919df317159d2))
* **form:** add checkbox to electric consumption form ([45877ae](https://github.com/EPFL-ENAC/co2-calculator/commit/45877aed24bd2818a33b7ac313161fe4392521fe))
* **frontend-module-table:** add inline input for module-table ([c3b24bd](https://github.com/EPFL-ENAC/co2-calculator/commit/c3b24bd5ad636895ff851db17341794bad54e293))
* **frontend:** add annual data import component ([524831a](https://github.com/EPFL-ENAC/co2-calculator/commit/524831a7d1d55ba7ae40ef5095a84ce1f0e6cae7))
* **frontend:** correct two dialogs for edit ([1c83893](https://github.com/EPFL-ENAC/co2-calculator/commit/1c83893dcdfc793f8a31977fd7dd76e23494e119))
* implement responsive grid layout for module forms ([c943f31](https://github.com/EPFL-ENAC/co2-calculator/commit/c943f31e9b5d83f71707ae86d1250b231f41c730))
* **module table:** add pagination to module table ([9e2406a](https://github.com/EPFL-ENAC/co2-calculator/commit/9e2406a6ebc09925a044817bfd4bd0600021f214))
* **module-table:** add data and edit/delete ([b67a868](https://github.com/EPFL-ENAC/co2-calculator/commit/b67a868fe389f38ca08983a7ee2eb81f2770bccc))
* refactored role provider interface for flexibility ([b22a422](https://github.com/EPFL-ENAC/co2-calculator/commit/b22a42222e64ec52d4fa95471a7659560679454e))
* refine module result card styling and layout ([692fede](https://github.com/EPFL-ENAC/co2-calculator/commit/692fedea4fdb8449a9b5a61512e668d6a17eeff3))
* **reporting:** add backoffice reporting UI with filters, module selectors, and export ([a6cf6df](https://github.com/EPFL-ENAC/co2-calculator/commit/a6cf6dfcbfb0627e29be1b4dfb1cfebf36919851))
* **responsive:** implement responsive grid breakpoints ([9128c11](https://github.com/EPFL-ENAC/co2-calculator/commit/9128c1181c351cde72e2c5d32340be60573eac20))
* **results:** implement results page ([162891b](https://github.com/EPFL-ENAC/co2-calculator/commit/162891b31f30dd20af15011a48052550619f13a2))
* **table:** add actions column with edit and delete buttons ([55d28a4](https://github.com/EPFL-ENAC/co2-calculator/commit/55d28a448d09ebb25cc1b7dec3115807d3cc1487))
* **table:** add CSV upload/download UI and improve table styling ([f368cbb](https://github.com/EPFL-ENAC/co2-calculator/commit/f368cbbe2518f7ea4948a1bb3537e3b76e9a7b9e))
* **tooltip:** redesign module title tooltips with design system tokens ([9dc1aed](https://github.com/EPFL-ENAC/co2-calculator/commit/9dc1aeda5e7af85e481a8b563ad990fb27f02dbd))
* translation issue in user management ([69d20bd](https://github.com/EPFL-ENAC/co2-calculator/commit/69d20bdc9fcdf3cc6a81ccae7ddb83607cc3b1bc))
* **update logos:** replace icons by provided SVGs ([5f74b54](https://github.com/EPFL-ENAC/co2-calculator/commit/5f74b54d50cf93a7efba521e447ceae38578a396))
* update npm ([e12cbe7](https://github.com/EPFL-ENAC/co2-calculator/commit/e12cbe75728a3d4631116ad984dcd966cd6cd964))
* **user management:** User management page for system and backoffice ([691ad01](https://github.com/EPFL-ENAC/co2-calculator/commit/691ad01cdb65a451c1a02acd833e13760740edad))
* **validate button:** wip ([f7b896f](https://github.com/EPFL-ENAC/co2-calculator/commit/f7b896f5b7bbb6c81fb941b6c1f1ab3e4501f6fe))

### Bug Fixes

* **#76-backend:** add coverage test for power_factors ([b3850f9](https://github.com/EPFL-ENAC/co2-calculator/commit/b3850f9cc885144293a90cb5576cf13685072d50))
* **#76-backend:** calculate based on hours/week ([7971795](https://github.com/EPFL-ENAC/co2-calculator/commit/79717954b4f4185db90f0d4e59ba23b077c99341))
* **#76-frontend:** add power factor ([ac2d2a4](https://github.com/EPFL-ENAC/co2-calculator/commit/ac2d2a4958f460b69596089880d56bebd56c9a0c))
* **backend:** correct equipment tests error ([25ac7cc](https://github.com/EPFL-ENAC/co2-calculator/commit/25ac7cc5a4efe5189ed26d12af8da3751fd73533))
* **backend:** generate erd from SQLModel ([e44ce36](https://github.com/EPFL-ENAC/co2-calculator/commit/e44ce363e0b5e55d4ab3739777a8335bfb8d32c7))
* correct faulty icons on module page ([f255984](https://github.com/EPFL-ENAC/co2-calculator/commit/f2559846c4d881a5b726f0e786c6df31d18d03e7))
* **frontend:** correct form and dialog ([bcf6ada](https://github.com/EPFL-ENAC/co2-calculator/commit/bcf6ada6f204580f2b5a7b683f0427ee3391b9d9))
* **frontend:** rename passive to standby ([569db16](https://github.com/EPFL-ENAC/co2-calculator/commit/569db1686a5fd5359e4f36a5147785e3bad216b5))
* integrate power factor resolution in equipment creation and update processes ([cdec629](https://github.com/EPFL-ENAC/co2-calculator/commit/cdec629698b2d5fd9219f8e4285cd96ccdb98ed5))
* **links:** make documentation edition links open in new tab ([bdc09cd](https://github.com/EPFL-ENAC/co2-calculator/commit/bdc09cd55ba82fe868974c399c032c15bd42dfeb))
* reinstate translations of data management ([57d09eb](https://github.com/EPFL-ENAC/co2-calculator/commit/57d09eb146b9c60e4b7f91fe176e4343fc09a10b))
* remove async_fallback param in db url because psycopg v3 does not support/need it ([c55c7b0](https://github.com/EPFL-ENAC/co2-calculator/commit/c55c7b05b1de0b7c67bb9ed6e3dba000552e5e72))
* **translation:** correct modules counter translation key on home page ([d564b82](https://github.com/EPFL-ENAC/co2-calculator/commit/d564b82e26bfa7968d862bd07f6fe8da723dbdb0))
* **translations:** fix translations on validation button ([7c43538](https://github.com/EPFL-ENAC/co2-calculator/commit/7c43538ed88223f7941648a0c155a0a6851735d8))

---

## [0.1.1](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.1.0...v0.1.1) (2025-11-28)

### Bug Fixes

* **release-please:** add config file for pre-bump major ([38a6b21](https://github.com/EPFL-ENAC/co2-calculator/commit/38a6b214d9a02098751ffd29d2fa89cb3a30f4b9))

---

## [0.1.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.0.1...v0.1.0) (2025-11-27)

### Features

* add guards ([50326f4](https://github.com/EPFL-ENAC/co2-calculator/commit/50326f45e80b4cc41e6c2eaa9ab2be9e890dc4f1))
* add localization section to README with translation guidelines ([f957535](https://github.com/EPFL-ENAC/co2-calculator/commit/f95753537eb5198cf6b5be4eee7b9c9bca4a20a7))
* add results button ([15edc47](https://github.com/EPFL-ENAC/co2-calculator/commit/15edc4718e6b60f73f54d80f2586f7e0833d1823))
* add workspace redirection guard and integrate into routing ([f2824d0](https://github.com/EPFL-ENAC/co2-calculator/commit/f2824d064154e795953aa192d4b576e901f572d7))
* **backend:** add behavior for affiliations and admin ([00941e2](https://github.com/EPFL-ENAC/co2-calculator/commit/00941e2ecd9c6f9206f544fbb6f6942671437187))
* **backend:** implement oauth2 login/logout/refresh/me /v1/auth endpoints ([28338fe](https://github.com/EPFL-ENAC/co2-calculator/commit/28338fe14ad2274320ff5034ef7084d2e684f0de))
* **backend:** mock units and unit/:id/results endpoints ([e5396a8](https://github.com/EPFL-ENAC/co2-calculator/commit/e5396a8ad48ec7fa885c272514b4020657d2fcec))
* change workspace button in header ([980d744](https://github.com/EPFL-ENAC/co2-calculator/commit/980d744af17c6b342c723adb8749d8804755d485))
* **database:** generate docs of erd schema ([01f9a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/01f9a4b24309633fc9ada3592f3bcf0694c41d6e))
* default local detection ([22db41a](https://github.com/EPFL-ENAC/co2-calculator/commit/22db41aafc89b57ac5bcf33ea9ca2f4c007788d6))
* **frontend:** add default routes ([41c4bb8](https://github.com/EPFL-ENAC/co2-calculator/commit/41c4bb849681463ddfc86734b975a3792b65eadc))
* **frontend:** add login + css ([f73c778](https://github.com/EPFL-ENAC/co2-calculator/commit/f73c778d2fdf29d5d0377d1416747473c461999d))
* improved overall design of header ([1ab8c68](https://github.com/EPFL-ENAC/co2-calculator/commit/1ab8c6887e12b54f504c43536116d843cc4f6f53))
* latest year ([a3cdb81](https://github.com/EPFL-ENAC/co2-calculator/commit/a3cdb81bddbab0f834df074b292ea11b1687668c))
* Loading data failure fallback ([2e05cfc](https://github.com/EPFL-ENAC/co2-calculator/commit/2e05cfc2e7dc0d2560fb138a98d7699966682d71))
* remove documentation tab from sidebar ([f746e24](https://github.com/EPFL-ENAC/co2-calculator/commit/f746e242f5b5ca8fedec1e422e6a3a68c46b79ee))
* sidebar menu for backoffice and system ([b0f0fbe](https://github.com/EPFL-ENAC/co2-calculator/commit/b0f0fbe4ac0dd8abf8520464fdbf8feaa25d4e04))
* timeline first draft ([ae842fe](https://github.com/EPFL-ENAC/co2-calculator/commit/ae842fe17b80455935dc1c57be06201b2ab3da16))
* translations and simplification of logic ([e9d67ab](https://github.com/EPFL-ENAC/co2-calculator/commit/e9d67ab23395aa81c049251ce21980123cc9ca98))
* UI with mock data ([c24bae2](https://github.com/EPFL-ENAC/co2-calculator/commit/c24bae21dcc21e3f885bf064a0bd836f44ca122a))
* workspace appearance logic done ([5536e9c](https://github.com/EPFL-ENAC/co2-calculator/commit/5536e9cc682a8b991e03243536ea148788c42011))

### Bug Fixes

* a few cosmetic changes ([84fa83c](https://github.com/EPFL-ENAC/co2-calculator/commit/84fa83c4e1df305547a6b2dfdfec5780e7670eb2))
* add missing itsdangerous dependency ([8233771](https://github.com/EPFL-ENAC/co2-calculator/commit/823377184639044f3ae7ca0d94575faaaf070425))
* **backend:** add Dockerfile ready for alembic migration ([43fa894](https://github.com/EPFL-ENAC/co2-calculator/commit/43fa894462bd59fbbaf3c05f34c71d0d0e389a72))
* **backend:** add env variable for docker-compose ([3f00d61](https://github.com/EPFL-ENAC/co2-calculator/commit/3f00d61c7783eb2edbcf7714c43ee9326dc4af1e))
* **boot:** simplify default language ([ad0d9e0](https://github.com/EPFL-ENAC/co2-calculator/commit/ad0d9e0de5c33aef4c514ea14b176c3583c4d1ef))
* broken font link ([194fd90](https://github.com/EPFL-ENAC/co2-calculator/commit/194fd90a654f53084c6cad0e4c0cd1de364331db))
* **ci:** correct npm cache path ([9fe548f](https://github.com/EPFL-ENAC/co2-calculator/commit/9fe548f964f2790ac750204ad929721849577031))
* **frontend:** move to port 8080 for non-root users ([0ff9cbd](https://github.com/EPFL-ENAC/co2-calculator/commit/0ff9cbdc1df04841f32fbfc2f7776e24d8c962fb))
* **helm:** add accred env variables ([62b714f](https://github.com/EPFL-ENAC/co2-calculator/commit/62b714f52d9e954adb12723657414ebca7556093))
* **helm:** add API_VERSION APP_VERSION and APP_NAME in helm ([19731ec](https://github.com/EPFL-ENAC/co2-calculator/commit/19731ec69d1dea29e0e03dd934c3e4b9cd139190))
* **helm:** add resource to migration init container ([3e4f8a9](https://github.com/EPFL-ENAC/co2-calculator/commit/3e4f8a922ede8833fd3fca10f0f4e578c719ff7a))
* **helm:** fix value path ([e0df3d5](https://github.com/EPFL-ENAC/co2-calculator/commit/e0df3d5136e748f443a21ef77586a84fdb934911))
* **log-injection:** from code-ql ([232bdb9](https://github.com/EPFL-ENAC/co2-calculator/commit/232bdb9035dc5c953c570968b6c56ab0194dbc3e))
* logo broken link ([c0e13e6](https://github.com/EPFL-ENAC/co2-calculator/commit/c0e13e650e35048f9408cbd350627861c2100d18))
        make timeline scrollable ([ba4d1b9](https://github.com/EPFL-ENAC/co2-calculator/commit/ba4d1b9972434f9e9e62ca92fb8f92d414cd8e95))
* no duplicates in login bg ([c360dd3](https://github.com/EPFL-ENAC/co2-calculator/commit/c360dd3be84ae0ff7364f8d0f1f634a475fa62a4))
* **pre-commit-hooks:** better error handling ([af7fee9](https://github.com/EPFL-ENAC/co2-calculator/commit/af7fee99aa1edabec0ca5d28a187615f08c8dda4))
* remove useless imports ([580b604](https://github.com/EPFL-ENAC/co2-calculator/commit/580b604e8c83e6133953ab9bbad0f450e142078c))
* simplify role mapping on units ([92a6aba](https://github.com/EPFL-ENAC/co2-calculator/commit/92a6abaebf7bf40d7b49ba84f87b8ef4f3aa304d))
* use parent/child for route + several small fixes ([1cef071](https://github.com/EPFL-ENAC/co2-calculator/commit/1cef071a54734c524237176c83f0d5f03fe462ab))
* use pinia persistent state instead of cookies ([a9414e6](https://github.com/EPFL-ENAC/co2-calculator/commit/a9414e60b98d2770b878750f2f0b82729e8534b3))