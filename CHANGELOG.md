# Changelog

## [0.3.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.2.0...v0.3.0)(2025-12-23)

## CO2 Calculator - Recent Development Summary

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


## [0.2.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.1.1...v0.2.0) (2025-12-23)


### Features

* add all roles to login test page [#183](https://github.com/EPFL-ENAC/co2-calculator/issues/183) ([#233](https://github.com/EPFL-ENAC/co2-calculator/issues/233)) ([194b4c1](https://github.com/EPFL-ENAC/co2-calculator/commit/194b4c125dc41e7a8c268dbd287e53be9eed92d0))
* add backoffice button in header ([7b10ebb](https://github.com/EPFL-ENAC/co2-calculator/commit/7b10ebb22f5a385526ee27ac481d7e0632486ed2))
* add distinct test users for each role name, based on User model ([89308ee](https://github.com/EPFL-ENAC/co2-calculator/commit/89308eef9d591acfe5cd0796e8d59d9839429599))
* add epfl favicons ([915935f](https://github.com/EPFL-ENAC/co2-calculator/commit/915935f5d3a8eb9f4254a4635f64b2a9cb4aa4dc))
* add lighthouse-plugin-ecoindex-core dependency to package.json and package-lock.json ([f9ddaff](https://github.com/EPFL-ENAC/co2-calculator/commit/f9ddaff1a1f50afb278b419dbab3457d32211b1f))
* add unit tests for backoffice API endpoints ([a92bf80](https://github.com/EPFL-ENAC/co2-calculator/commit/a92bf806b435fc69f10219d52fd0c16edd514214))
* **backend:** correct seed with default value ([4141e03](https://github.com/EPFL-ENAC/co2-calculator/commit/4141e03fa4519250f45fd323511a9b65568bf6b6))
* **backoffice:** add backoffice API endpoints and reporting functionality ([31d2970](https://github.com/EPFL-ENAC/co2-calculator/commit/31d2970bca6b9b92fa4e20bca683d2f2eebcc7d5))
* **collapsible:** add collapsible sections ([0e0b82a](https://github.com/EPFL-ENAC/co2-calculator/commit/0e0b82a3070f2cb35fc807675f810db8ee2b55b8))
* **conso-elec-table:** add basic layout/structure for modules and submodules ([97b7991](https://github.com/EPFL-ENAC/co2-calculator/commit/97b799124a947242b7732375ffaad77889d3259b))
* **conso-elec-table:** hide other module tables ([b07f370](https://github.com/EPFL-ENAC/co2-calculator/commit/b07f3708a2129f107a8c3105c99fc54bf288fedd))
* **conso-elec-table:** hide unused module and center total results ([4823850](https://github.com/EPFL-ENAC/co2-calculator/commit/4823850ccbecccc038ce4d3bb080d122c68d4715))
* **conso-elec-table:** implement backend several endpoints ([5f4b33a](https://github.com/EPFL-ENAC/co2-calculator/commit/5f4b33a6f946f4516167cd9d04779f5ee57643d6))
* **conso-elec-table:** retrieve mock from backend ([6b8c96d](https://github.com/EPFL-ENAC/co2-calculator/commit/6b8c96dd1d31c1b890f4b25938c6edaeb769ac55))
* **database:** add PostgreSQL management commands and update foreign key constraints ([b702dae](https://github.com/EPFL-ENAC/co2-calculator/commit/b702dae0f52f2099b86bad81b9ebe65e97fa41eb))
* **database:** add PostgreSQL management commands and update foreign… ([#186](https://github.com/EPFL-ENAC/co2-calculator/issues/186)) ([6fa1c9c](https://github.com/EPFL-ENAC/co2-calculator/commit/6fa1c9ca8ab399e9f81a45885ffa017fec6ee249))
* **delete dialog:** add delete confirmation dialog to ModuleTable ([ce543d1](https://github.com/EPFL-ENAC/co2-calculator/commit/ce543d12158ff1b4265759e0030b7cb337eb0fe1))
* disable access in backoffice navigaiion for backoffice standard ([f4b4798](https://github.com/EPFL-ENAC/co2-calculator/commit/f4b479864ef040ba2db0844f0808b17e02c2d9b5))
* **documentation-editing:** add documentatin editing content ([c631a79](https://github.com/EPFL-ENAC/co2-calculator/commit/c631a794f16e5a365e26f9d16eb11e4d1a7f1c12))
* **equipment:** add class-subclass map endpoint and refactor power ([3e960d2](https://github.com/EPFL-ENAC/co2-calculator/commit/3e960d25f8af5c38b9cc2f843df919df317159d2))
* **form:** add checkbox to electric consumption form ([45877ae](https://github.com/EPFL-ENAC/co2-calculator/commit/45877aed24bd2818a33b7ac313161fe4392521fe))
* **frontend-module-equipement-electric:** add module charts ([0263613](https://github.com/EPFL-ENAC/co2-calculator/commit/02636134c57015fc4037a6aa88975778fe9d83c8))
* **frontend-module-equipement-electric:** add module title component ([0a2f6c6](https://github.com/EPFL-ENAC/co2-calculator/commit/0a2f6c6012eec2f739263d27fa2250ac06c1c8b9))
* **frontend-module-table:** add inline input for module-table ([c3b24bd](https://github.com/EPFL-ENAC/co2-calculator/commit/c3b24bd5ad636895ff851db17341794bad54e293))
* **frontend-module-table:** add inline input for module-table ([#201](https://github.com/EPFL-ENAC/co2-calculator/issues/201)) ([3e3a4fc](https://github.com/EPFL-ENAC/co2-calculator/commit/3e3a4fc479585d3a92e540a67dcf4998c212567e))
* **frontend-module:** add draft configuration for modules ([a8d28f4](https://github.com/EPFL-ENAC/co2-calculator/commit/a8d28f45ceffc52721367ae5cb5f4043f575d3c9))
* **frontend:** add annual data import component, no backend ([524831a](https://github.com/EPFL-ENAC/co2-calculator/commit/524831a7d1d55ba7ae40ef5095a84ce1f0e6cae7))
* **frontend:** add annual data import component, no backend ([#146](https://github.com/EPFL-ENAC/co2-calculator/issues/146)) ([6263912](https://github.com/EPFL-ENAC/co2-calculator/commit/6263912bcb1a8e3e1f375fa49d3371b7a97bb5ff))
* **frontend:** correct two dialog for edit ([1c83893](https://github.com/EPFL-ENAC/co2-calculator/commit/1c83893dcdfc793f8a31977fd7dd76e23494e119))
* implement responsive grid layout for module forms ([c943f31](https://github.com/EPFL-ENAC/co2-calculator/commit/c943f31e9b5d83f71707ae86d1250b231f41c730))
* **module table:** add pagination to module table ([9e2406a](https://github.com/EPFL-ENAC/co2-calculator/commit/9e2406a6ebc09925a044817bfd4bd0600021f214))
* **module-add-modal:** add proper css for modal ([7abfdc7](https://github.com/EPFL-ENAC/co2-calculator/commit/7abfdc7dba1f1285f00229e3848a83611c16b037))
* **module-table:** add data and edit/delete ([b67a868](https://github.com/EPFL-ENAC/co2-calculator/commit/b67a868fe389f38ca08983a7ee2eb81f2770bccc))
* **module-table:** change name of slotProps to avoid confusion ([d89cb0e](https://github.com/EPFL-ENAC/co2-calculator/commit/d89cb0ecaf23daab01874eb80778c4c9588a1330))
* refactored role provider interface for flexibility ([b22a422](https://github.com/EPFL-ENAC/co2-calculator/commit/b22a42222e64ec52d4fa95471a7659560679454e))
* refine module result card styling and layout ([692fede](https://github.com/EPFL-ENAC/co2-calculator/commit/692fedea4fdb8449a9b5a61512e668d6a17eeff3))
* refines module title styling ([1332fa8](https://github.com/EPFL-ENAC/co2-calculator/commit/1332fa848d7a87153822e3287834c2a208836810))
* remove duplicate icons ([5f74b54](https://github.com/EPFL-ENAC/co2-calculator/commit/5f74b54d50cf93a7efba521e447ceae38578a396))
* **reporting:** add backoffice reporting UI with filters, module selectors, and export ([a6cf6df](https://github.com/EPFL-ENAC/co2-calculator/commit/a6cf6dfcbfb0627e29be1b4dfb1cfebf36919851))
* **responsive:** implement responsive grid breakpoints ([9128c11](https://github.com/EPFL-ENAC/co2-calculator/commit/9128c1181c351cde72e2c5d32340be60573eac20))
* **results:** implement results page ([162891b](https://github.com/EPFL-ENAC/co2-calculator/commit/162891b31f30dd20af15011a48052550619f13a2))
* **table:** add actions column with edit and delete buttons  - Add "Actions" column to all module tables (right-aligned) - Add edit and delete icon buttons in each table row - Add align property to TableColumn interface (left/right/center) - Update equipment-electric-consumption config with column alignment - Add square-button styling for compact action buttons - Add common_actions i18n translation - Actions are placeholders for upcoming edit/delete functionality ([55d28a4](https://github.com/EPFL-ENAC/co2-calculator/commit/55d28a448d09ebb25cc1b7dec3115807d3cc1487))
* **table:** add CSV upload/download UI and improve table styling ([f368cbb](https://github.com/EPFL-ENAC/co2-calculator/commit/f368cbbe2518f7ea4948a1bb3537e3b76e9a7b9e))
* **tooltip:** redesign module title tooltips with design system tokens ([9dc1aed](https://github.com/EPFL-ENAC/co2-calculator/commit/9dc1aeda5e7af85e481a8b563ad990fb27f02dbd))
* translation issue in userr management ([69d20bd](https://github.com/EPFL-ENAC/co2-calculator/commit/69d20bdc9fcdf3cc6a81ccae7ddb83607cc3b1bc))
* **update logos:** replace icons by provided svg's ([5f74b54](https://github.com/EPFL-ENAC/co2-calculator/commit/5f74b54d50cf93a7efba521e447ceae38578a396))
* update npm ([e12cbe7](https://github.com/EPFL-ENAC/co2-calculator/commit/e12cbe75728a3d4631116ad984dcd966cd6cd964))
* **user management:** Usermanagmeent page for system and backooffice ([691ad01](https://github.com/EPFL-ENAC/co2-calculator/commit/691ad01cdb65a451c1a02acd833e13760740edad))
* **validate button:** wip ([f7b896f](https://github.com/EPFL-ENAC/co2-calculator/commit/f7b896f5b7bbb6c81fb941b6c1f1ab3e4501f6fe))


### Bug Fixes

* **#76-backend:** add coverage test for power_factors ([b3850f9](https://github.com/EPFL-ENAC/co2-calculator/commit/b3850f9cc885144293a90cb5576cf13685072d50))
* **#76-backend:** calculate based on hours/week ([7971795](https://github.com/EPFL-ENAC/co2-calculator/commit/79717954b4f4185db90f0d4e59ba23b077c99341))
* **#76-backend:** calculate based on hours/week ([#254](https://github.com/EPFL-ENAC/co2-calculator/issues/254)) ([94c7c4e](https://github.com/EPFL-ENAC/co2-calculator/commit/94c7c4ec40a8803ab5d53f3c5666900cede68cbd))
* **#76-backend:** remove unwanted side effects ([da186ef](https://github.com/EPFL-ENAC/co2-calculator/commit/da186ef502201da49f4b21cd024b4ebe47f07bf1))
* **#76-frontend:** add power factor ([ac2d2a4](https://github.com/EPFL-ENAC/co2-calculator/commit/ac2d2a4958f460b69596089880d56bebd56c9a0c))
* **#76-frontend:** add power factor sub class required ([6f51eb3](https://github.com/EPFL-ENAC/co2-calculator/commit/6f51eb3396aad0da6cce52f12b5173f7640bb8d2))
* **#76-frontend:** correct typo ([e564825](https://github.com/EPFL-ENAC/co2-calculator/commit/e5648256b7675e750ccd8439e495aa7d651ba57a))
* **#76:** latest changes asked ([d666fad](https://github.com/EPFL-ENAC/co2-calculator/commit/d666fad4a05a43e8f28bc6ec3a7579efb5200062))
* add old role temporarily ([f15f2a3](https://github.com/EPFL-ENAC/co2-calculator/commit/f15f2a31f2a1af26cc8b65b80058c3c315882b96))
* **backend:** correct equipment tests error ([25ac7cc](https://github.com/EPFL-ENAC/co2-calculator/commit/25ac7cc5a4efe5189ed26d12af8da3751fd73533))
* **backend:** generate erd from SQLModel ([e44ce36](https://github.com/EPFL-ENAC/co2-calculator/commit/e44ce363e0b5e55d4ab3739777a8335bfb8d32c7))
* correct fawlty icons on module page ([f255984](https://github.com/EPFL-ENAC/co2-calculator/commit/f2559846c4d881a5b726f0e786c6df31d18d03e7))
* correct typos ([2807b3c](https://github.com/EPFL-ENAC/co2-calculator/commit/2807b3ce4478025361c7d76896de497628761520))
* format text ([262c122](https://github.com/EPFL-ENAC/co2-calculator/commit/262c1224af9bfd1d65e231b93b13bcc68301865e))
* **frontend-icons:** remove useless code [#98](https://github.com/EPFL-ENAC/co2-calculator/issues/98) ([79da44c](https://github.com/EPFL-ENAC/co2-calculator/commit/79da44c643be4289c9e6e0b93eea320daf31a82f))
* **frontend:** correct form and dialog ([bcf6ada](https://github.com/EPFL-ENAC/co2-calculator/commit/bcf6ada6f204580f2b5a7b683f0427ee3391b9d9))
* **frontend:** rename passive to standby ([569db16](https://github.com/EPFL-ENAC/co2-calculator/commit/569db1686a5fd5359e4f36a5147785e3bad216b5))
* **helm values:** add backend default env ([1db6644](https://github.com/EPFL-ENAC/co2-calculator/commit/1db6644549ed19046a44c84bd4b4664f325ce502))
* **helm values:** add backend default env ([#167](https://github.com/EPFL-ENAC/co2-calculator/issues/167)) ([d5eea57](https://github.com/EPFL-ENAC/co2-calculator/commit/d5eea57a98441b5c61ac0e2fe86bea20f515e8f1))
* integrate power factor resolution in equipment creation and update processes ([cdec629](https://github.com/EPFL-ENAC/co2-calculator/commit/cdec629698b2d5fd9219f8e4285cd96ccdb98ed5))
* **links:** make documentation edition links open in new tab ([bdc09cd](https://github.com/EPFL-ENAC/co2-calculator/commit/bdc09cd55ba82fe868974c399c032c15bd42dfeb))
* reinstate translations of data management ([57d09eb](https://github.com/EPFL-ENAC/co2-calculator/commit/57d09eb146b9c60e4b7f91fe176e4343fc09a10b))
* reinstate translations of data management ([#187](https://github.com/EPFL-ENAC/co2-calculator/issues/187)) ([7916326](https://github.com/EPFL-ENAC/co2-calculator/commit/79163267e108db6b48e383f7ee7ea0b7adb8c81b))
* remove async_fallback param in db url because psycopg v3 does not support/need it ([c55c7b0](https://github.com/EPFL-ENAC/co2-calculator/commit/c55c7b05b1de0b7c67bb9ed6e3dba000552e5e72))
* remove commented border style and improve condition check in useModulePowerFactors ([a6f26e1](https://github.com/EPFL-ENAC/co2-calculator/commit/a6f26e10b330e036d31b9efa047f82a85fca6e98))
* remove unnecessary dependencies and ensure proper formatting in package.json ([8da9feb](https://github.com/EPFL-ENAC/co2-calculator/commit/8da9feb42107ed4f0acbc4d5df82bdf3ae77bb36))
* **transation:** add missing user managmement transations for system and backoffice ([3baca28](https://github.com/EPFL-ENAC/co2-calculator/commit/3baca28ecceee61aa64719cf6a19b7cc729695f1))
* **translation:** correct modules counter translation key on home page ([d564b82](https://github.com/EPFL-ENAC/co2-calculator/commit/d564b82e26bfa7968d862bd07f6fe8da723dbdb0))
* **translation:** correct modules counter translation key on home page ([#191](https://github.com/EPFL-ENAC/co2-calculator/issues/191)) ([d4bf4c8](https://github.com/EPFL-ENAC/co2-calculator/commit/d4bf4c8252763a1521e029ea7eb58be2c5bf9a11))
* **translations:** fix translations on validatation button ([7c43538](https://github.com/EPFL-ENAC/co2-calculator/commit/7c43538ed88223f7941648a0c155a0a6851735d8))
* **translations:** fix translations on validatation button ([#200](https://github.com/EPFL-ENAC/co2-calculator/issues/200)) ([010980f](https://github.com/EPFL-ENAC/co2-calculator/commit/010980f046e8dffe7e1b2136b324e032ec5e38ab))
* update Codecov badge link in README.md ([3d65cd8](https://github.com/EPFL-ENAC/co2-calculator/commit/3d65cd809c0d4a029b007ed9bf7e1ef033448c68))
* update Codecov badge link in README.md ([#255](https://github.com/EPFL-ENAC/co2-calculator/issues/255)) ([83c0c63](https://github.com/EPFL-ENAC/co2-calculator/commit/83c0c6357783e6c1856dc2f4ce9787f9de2af2cf))
* update installation step for Lighthouse plugin in workflow ([dcc5c49](https://github.com/EPFL-ENAC/co2-calculator/commit/dcc5c49d6f922fbf4f76744033d1079750ef4d8c))
* update plugin path for lighthouse in .lighthouserc.json ([ebc13a0](https://github.com/EPFL-ENAC/co2-calculator/commit/ebc13a0f386524aa77b876ff3446827bc5284c61))
* update plugin path for lighthouse in .lighthouserc.json ([1ece653](https://github.com/EPFL-ENAC/co2-calculator/commit/1ece653b8b79a8911e78179876ba725ddff28b56))

## [0.1.1](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.1.0...v0.1.1) (2025-11-28)


### Bug Fixes

* **release-please:** add config file for pre-bump major ([38a6b21](https://github.com/EPFL-ENAC/co2-calculator/commit/38a6b214d9a02098751ffd29d2fa89cb3a30f4b9))
* **release-please:** add config file for pre-bump major ([#161](https://github.com/EPFL-ENAC/co2-calculator/issues/161)) ([646f42e](https://github.com/EPFL-ENAC/co2-calculator/commit/646f42e301b57c9e4cc299f9c1d3b6fc5e711c8b))


### feat
- feat: Adding links to edit buttons
- feat(backend): make test user when refresh or get current user are called #114
- feat(frontend): add module thershold configuration #43
- feat: redirect from workspace setup
- feat: added page header component based on sidebar nav item
- feat: module management page
- feat: added test login entry point and role for development #114

### fix
- fix: correct link
- fix: add links + small translation change
- fix: changing texts in workspace setup
- fix: changing texts in workspace setup
- fix(frontend): if loggedIn and in /login or /login-test redirect to default
Functions prefixed with underscore are considered private to their module.
- fix(login-refresh): correct mypy typecheck
- fix(frontend): no more scroll top on route replace/push
- fix(frontend): remove and add better guard for default redirect
- fix: fixed a few worspace issues
- fix: adjust class positioning and checkbox label in ModuleManagementPage
- fix(helm): add resources to backend init
- fix(frontend): add potential fix for code scanning alert no. 69: Log Injection
Co-authored-by: Copilot Autofix powered by AI <62310815+github-advanced-security[bot]@users.noreply.github.com>

### docs
- docs: add eco-design section and update navigation
- docs: rewrite ecoconception
- docs: rewrite ecoconception

### chore
- chore(ci): validate only security on pull request
- chore(frontend): remove useless/duplicate call to getUnitResults
- chore: make format
- chore(tests): add enough unit and integration tests to pass 100% coverage
- chore(backend): make test fail <60% of coverage
- chore(backend-coverage): add codecov token
- chore(backend-coverage): add coverage xml

### refactor
- refactor(security): rename _make_test_user to make_test_user for consistency

### test
- fix(frontend): if loggedIn and in /login or /login-test redirect to default
- refactor(security): rename _make_test_user to make_test_user for consistency
Importing _make_test_user violates Python naming conventions.
- feat(backend): make test user when refresh or get current user are called #114
- chore(tests): add enough unit and integration tests to pass 100% coverage
- chore(backend): make test fail <60% of coverage
- feat: added test login entry point and role for development #114



## 0.1.0 (2025-11-27)


### Features

* `make help-requirements` ([72cfc24](https://github.com/EPFL-ENAC/co2-calculator/commit/72cfc24cae94c91ae26f91ee95f92e892c2d967f))
* add guards ([50326f4](https://github.com/EPFL-ENAC/co2-calculator/commit/50326f45e80b4cc41e6c2eaa9ab2be9e890dc4f1))
* add localization section to README with translation guidelines ([f957535](https://github.com/EPFL-ENAC/co2-calculator/commit/f95753537eb5198cf6b5be4eee7b9c9bca4a20a7))
* add results button ([15edc47](https://github.com/EPFL-ENAC/co2-calculator/commit/15edc4718e6b60f73f54d80f2586f7e0833d1823))
* add workspace redirection guard and integrate into routing ([f2824d0](https://github.com/EPFL-ENAC/co2-calculator/commit/f2824d064154e795953aa192d4b576e901f572d7))
* **backend:** add behavior for affiliations and admin ([00941e2](https://github.com/EPFL-ENAC/co2-calculator/commit/00941e2ecd9c6f9206f544fbb6f6942671437187))
* **backend:** implement oauth2 login/logout/refresh/me /v1/auth endpoints ([28338fe](https://github.com/EPFL-ENAC/co2-calculator/commit/28338fe14ad2274320ff5034ef7084d2e684f0de))
* **backend:** mock units and unit/:id/results endpoints ([e5396a8](https://github.com/EPFL-ENAC/co2-calculator/commit/e5396a8ad48ec7fa885c272514b4020657d2fcec))
* change worspace button in header ([980d744](https://github.com/EPFL-ENAC/co2-calculator/commit/980d744af17c6b342c723adb8749d8804755d485))
* **database:** generate docs of erd schema ([01f9a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/01f9a4b24309633fc9ada3592f3bcf0694c41d6e))
* default local detection ([22db41a](https://github.com/EPFL-ENAC/co2-calculator/commit/22db41aafc89b57ac5bcf33ea9ca2f4c007788d6))
* **frontend:** add default routes ([41c4bb8](https://github.com/EPFL-ENAC/co2-calculator/commit/41c4bb849681463ddfc86734b975a3792b65eadc))
* **frontend:** add home Page Layout (PR [#102](https://github.com/EPFL-ENAC/co2-calculator/issues/102)) (Issue [#13](https://github.com/EPFL-ENAC/co2-calculator/issues/13)) ([d852628](https://github.com/EPFL-ENAC/co2-calculator/commit/d8526289bc4d4e7ccf9d84ec90458d67ce1b585f))
* **frontend:** add login + css ([f73c778](https://github.com/EPFL-ENAC/co2-calculator/commit/f73c778d2fdf29d5d0377d1416747473c461999d))
* Home Page Layout ([f8c3a31](https://github.com/EPFL-ENAC/co2-calculator/commit/f8c3a3158575be5b3a6f6ffa8515a8c987a8d1ca))
* improved overal design of header ([1ab8c68](https://github.com/EPFL-ENAC/co2-calculator/commit/1ab8c6887e12b54f504c43536116d843cc4f6f53))
* latest year ([a3cdb81](https://github.com/EPFL-ENAC/co2-calculator/commit/a3cdb81bddbab0f834df074b292ea11b1687668c))
* Loading data failure fallback ([2e05cfc](https://github.com/EPFL-ENAC/co2-calculator/commit/2e05cfc2e7dc0d2560fb138a98d7699966682d71))
* remove documentatio tab from sidebar ([f746e24](https://github.com/EPFL-ENAC/co2-calculator/commit/f746e242f5b5ca8fedec1e422e6a3a68c46b79ee))
* sidebar menu for backoffice and system ([b0f0fbe](https://github.com/EPFL-ENAC/co2-calculator/commit/b0f0fbe4ac0dd8abf8520464fdbf8feaa25d4e04))
* timeline first draft ([ae842fe](https://github.com/EPFL-ENAC/co2-calculator/commit/ae842fe17b80455935dc1c57be06201b2ab3da16))
* timeline improved layout ([0d6a474](https://github.com/EPFL-ENAC/co2-calculator/commit/0d6a4742936d522d629d7b746ba4f4aad17f3a65))
* translations and simplificaiton of logic ([e9d67ab](https://github.com/EPFL-ENAC/co2-calculator/commit/e9d67ab23395aa81c049251ce21980123cc9ca98))
* UI With mock data ([c24bae2](https://github.com/EPFL-ENAC/co2-calculator/commit/c24bae21dcc21e3f885bf064a0bd836f44ca122a))
* workspace appearance logic done ([5536e9c](https://github.com/EPFL-ENAC/co2-calculator/commit/5536e9cc682a8b991e03243536ea148788c42011))
* **workspace:** change update_at type for unit_results mock in backend ([4e068db](https://github.com/EPFL-ENAC/co2-calculator/commit/4e068db9db0d8e55c39b937804de4fb76ee790fa))


### Bug Fixes

* a few cosmetic changes ([84fa83c](https://github.com/EPFL-ENAC/co2-calculator/commit/84fa83c4e1df305547a6b2dfdfec5780e7670eb2))
* a few cosmetic changes ([059a63d](https://github.com/EPFL-ENAC/co2-calculator/commit/059a63d2051f1d207c0d107f8e72d3c86e84f5ad))
* A few cosmetic changes ([e8fe0eb](https://github.com/EPFL-ENAC/co2-calculator/commit/e8fe0ebe134c9135dde2a0c72cc3b27af37e40ee))
* actual Markdown ([be16639](https://github.com/EPFL-ENAC/co2-calculator/commit/be16639aacb50ee07d8958081c5c0b0c52e3df57))
* add missing itsdangerous dependency ([8233771](https://github.com/EPFL-ENAC/co2-calculator/commit/823377184639044f3ae7ca0d94575faaaf070425))
* add missing itsdangerous dependency to lock file ([f1dba26](https://github.com/EPFL-ENAC/co2-calculator/commit/f1dba261171fe889d5127fb695525d211e8ec51c))
* Added computer table header fro translations ([91132a3](https://github.com/EPFL-ENAC/co2-calculator/commit/91132a3b7547cc3cba2472edf94c6a771b1d1ec6))
* **backend-integration-test:** mock oauth2 response ([d6b5636](https://github.com/EPFL-ENAC/co2-calculator/commit/d6b56361cd36d0dad1aa2473fcd9651aa2bb83ac))
* **backend:** add Dockerfile ready for alembic migration ([43fa894](https://github.com/EPFL-ENAC/co2-calculator/commit/43fa894462bd59fbbaf3c05f34c71d0d0e389a72))
* **backend:** add env variable for docker-compose ([3f00d61](https://github.com/EPFL-ENAC/co2-calculator/commit/3f00d61c7783eb2edbcf7714c43ee9326dc4af1e))
* **backend:** remove redundant assignment ([ac845d8](https://github.com/EPFL-ENAC/co2-calculator/commit/ac845d8281ae3191228a9db3af2da83e57e63557))
* **boot:** simplify default language ([ad0d9e0](https://github.com/EPFL-ENAC/co2-calculator/commit/ad0d9e0de5c33aef4c514ea14b176c3583c4d1ef))
* broken font link ([194fd90](https://github.com/EPFL-ENAC/co2-calculator/commit/194fd90a654f53084c6cad0e4c0cd1de364331db))
* canard header ([e98001f](https://github.com/EPFL-ENAC/co2-calculator/commit/e98001f744bb3e91f5e4064686e90612099c23a7))
* **ci:** correct npm cache path ([9fe548f](https://github.com/EPFL-ENAC/co2-calculator/commit/9fe548f964f2790ac750204ad929721849577031))
* **ci:** deploy via artficat instead of branch ([a835c1c](https://github.com/EPFL-ENAC/co2-calculator/commit/a835c1ce282773bcf1de86ffc8b42adc5a576f7b))
* code reiew remarks ([543f40e](https://github.com/EPFL-ENAC/co2-calculator/commit/543f40ef1d38701ca04650873de609287abeada9))
* code review remarks ([3f17b00](https://github.com/EPFL-ENAC/co2-calculator/commit/3f17b006ae7f5b8226027cc33a0a591b275eee7e))
* code review remarks ([06d4280](https://github.com/EPFL-ENAC/co2-calculator/commit/06d42802aaff630ef765d94b9b5299cdf1f84f66))
* code review remarks ([8d23760](https://github.com/EPFL-ENAC/co2-calculator/commit/8d23760d87e6d43ca4503ae4c4e1a0c8c15f0504))
* compute sidebar ([d8029ce](https://github.com/EPFL-ENAC/co2-calculator/commit/d8029ce89acfd03d1431fbcbf35ed9e55c693276))
* conflicts ([02f202a](https://github.com/EPFL-ENAC/co2-calculator/commit/02f202a0cfa217aa4a67267a939057f604adb4e4))
* correct menu items ([b325ab4](https://github.com/EPFL-ENAC/co2-calculator/commit/b325ab45310db3e4c2d60391d6b9eadbc78d5c19))
* cosmetic changes ([c30b047](https://github.com/EPFL-ENAC/co2-calculator/commit/c30b047fd47e130fc76e1710aba1860621d0b424))
* cosmetic changes ([c7f4bda](https://github.com/EPFL-ENAC/co2-calculator/commit/c7f4bda9ddb52a883ef2b94db2b0f1961ed3dec6))
* fix linting errors ([295d786](https://github.com/EPFL-ENAC/co2-calculator/commit/295d78664e9b0fa880caae79e476cde9bac47700))
* fixing translation logic ([8627408](https://github.com/EPFL-ENAC/co2-calculator/commit/8627408ae3630279c5f1bcd58ae3dde06fb24675))
* **frontend-workspace:** authGuard type-check proper role ([09eeb31](https://github.com/EPFL-ENAC/co2-calculator/commit/09eeb31e0f5d9bb7be43787bd0244a7a2e63d6ab))
* **frontend:** correct bridge ([cb5131d](https://github.com/EPFL-ENAC/co2-calculator/commit/cb5131ddac7856af2ab9c3080dc2c84b41744969))
* **frontend:** generate scss from tokens ([91d6f99](https://github.com/EPFL-ENAC/co2-calculator/commit/91d6f994e1eef5ddd4e0ad0e9ad73add46e60259))
* **frontend:** move to port 8080 for non-root users ([0ff9cbd](https://github.com/EPFL-ENAC/co2-calculator/commit/0ff9cbdc1df04841f32fbfc2f7776e24d8c962fb))
* **frontend:** no more stylelint issue ([e9f0920](https://github.com/EPFL-ENAC/co2-calculator/commit/e9f09202d7f8ceeab198ab5b71607a95d0373cf7))
* **frontend:** remove buggy tokens ([af0096b](https://github.com/EPFL-ENAC/co2-calculator/commit/af0096b5e548dc172ae97c62f87e7ec2a4ebe92b))
* **frontend:** update frontend/src/boot/i18n.ts ([9753072](https://github.com/EPFL-ENAC/co2-calculator/commit/975307298b29cdcdcf23248706566df390baafed))
* **frontend:** use const as enum-like for moduleState ([45e7381](https://github.com/EPFL-ENAC/co2-calculator/commit/45e7381ded29313b4b3958b466e99c8919226b9a))
* **helm:** add accred env variables ([62b714f](https://github.com/EPFL-ENAC/co2-calculator/commit/62b714f52d9e954adb12723657414ebca7556093))
* **helm:** add accred env variables and secrets ([2f3cc35](https://github.com/EPFL-ENAC/co2-calculator/commit/2f3cc3511bf7ebf9d1583bce79cd05376a6be548))
* **helm:** add API_VERSION APP_VERSION and APP_NAME in helm ([19731ec](https://github.com/EPFL-ENAC/co2-calculator/commit/19731ec69d1dea29e0e03dd934c3e4b9cd139190))
* **helm:** add resource to migration init container ([3e4f8a9](https://github.com/EPFL-ENAC/co2-calculator/commit/3e4f8a922ede8833fd3fca10f0f4e578c719ff7a))
* **helm:** add resource to migration init container ([#120](https://github.com/EPFL-ENAC/co2-calculator/issues/120)) ([0b88cb4](https://github.com/EPFL-ENAC/co2-calculator/commit/0b88cb40ea50523693a0f9aca58df22ba4dd87ed))
* **helm:** add resources for migration job ([1b3ce14](https://github.com/EPFL-ENAC/co2-calculator/commit/1b3ce14509609448f2527a397b9c932c541d1316))
* **helm:** add resources for migration job ([#119](https://github.com/EPFL-ENAC/co2-calculator/issues/119)) ([1fa65a8](https://github.com/EPFL-ENAC/co2-calculator/commit/1fa65a823f37e5621ea28d4ae213652373ff4594))
* **helm:** add resources to backend init ([474ff06](https://github.com/EPFL-ENAC/co2-calculator/commit/474ff06832ed1c506dab3c28cff3ca155ec0114d))
* **helm:** add resources to backend init ([#126](https://github.com/EPFL-ENAC/co2-calculator/issues/126)) ([d8fa94e](https://github.com/EPFL-ENAC/co2-calculator/commit/d8fa94e94f87b75a9179ef05878e768691ad6d57))
* **helm:** default values was too much of a security risk ([d857943](https://github.com/EPFL-ENAC/co2-calculator/commit/d857943401d2454f09d9d6d1c2465675636c58a5))
* **helm:** fix value path ([e0df3d5](https://github.com/EPFL-ENAC/co2-calculator/commit/e0df3d5136e748f443a21ef77586a84fdb934911))
* Improving types ([8f8ba9d](https://github.com/EPFL-ENAC/co2-calculator/commit/8f8ba9d07fd3574087d818a82ea0e1526220cbb6))
* layout ([4b68f8a](https://github.com/EPFL-ENAC/co2-calculator/commit/4b68f8afbfb5d992965719e72683388546060496))
* **log-injection:** from code-ql ([232bdb9](https://github.com/EPFL-ENAC/co2-calculator/commit/232bdb9035dc5c953c570968b6c56ab0194dbc3e))
* **log-injection:** from code-ql ([17ba158](https://github.com/EPFL-ENAC/co2-calculator/commit/17ba158099f7fdc69c0ed4732c1f667829c06cac))
* **log-injection:** from code-ql ([fbf0647](https://github.com/EPFL-ENAC/co2-calculator/commit/fbf06477fc92a01983eaf46bee384c57794f3010))
* logo broken link ([c0e13e6](https://github.com/EPFL-ENAC/co2-calculator/commit/c0e13e650e35048f9408cbd350627861c2100d18))
* make timeline scrollable ([ba4d1b9](https://github.com/EPFL-ENAC/co2-calculator/commit/ba4d1b9972434f9e9e62ca92fb8f92d414cd8e95))
* no duplicates in login bg ([c360dd3](https://github.com/EPFL-ENAC/co2-calculator/commit/c360dd3be84ae0ff7364f8d0f1f634a475fa62a4))
* passing code formatting test ([45bfdb9](https://github.com/EPFL-ENAC/co2-calculator/commit/45bfdb9dd4f721c9dbd89240a421cdc76ff89cb3))
* PR comments ([2929c15](https://github.com/EPFL-ENAC/co2-calculator/commit/2929c15ee10849fa8c4c21aaac14d5fcfd27ec8d))
* PR comments ([f31b100](https://github.com/EPFL-ENAC/co2-calculator/commit/f31b1001d295deb19aa1ad3a50970199e399c572))
* **pre-commit-hooks:** better error handling ([af7fee9](https://github.com/EPFL-ENAC/co2-calculator/commit/af7fee99aa1edabec0ca5d28a187615f08c8dda4))
* push before rebase ([034f92c](https://github.com/EPFL-ENAC/co2-calculator/commit/034f92c75a0e890fe1bfff260cf8b073469a3776))
* quality-check ([dfa9620](https://github.com/EPFL-ENAC/co2-calculator/commit/dfa9620cb6820db413542606cab39704e61c82c0))
* **quasar-css-layer:** put quasar inside a layer ([f3c0aab](https://github.com/EPFL-ENAC/co2-calculator/commit/f3c0aab7b14ec3c180f77f97f68f85904dd62f2f))
* Redirect when going to upper level in the page hierarchy ([30eda9e](https://github.com/EPFL-ENAC/co2-calculator/commit/30eda9ed5f678ae0f5248e517ed5b7e6d76dcc66))
* remove comments referencing tokens.css ([350c355](https://github.com/EPFL-ENAC/co2-calculator/commit/350c355b38fafd27c537d615e9a37961cb957582))
* remove generated design tokens ([2a0395e](https://github.com/EPFL-ENAC/co2-calculator/commit/2a0395e69877d45b005a7df3fcb64dd9808d04b3))
* remove generated design tokens ([#103](https://github.com/EPFL-ENAC/co2-calculator/issues/103)) ([2a798b1](https://github.com/EPFL-ENAC/co2-calculator/commit/2a798b10312d1601cf3bc8fd12790a9d358800a8))
* remove mocks ([8f4e7b5](https://github.com/EPFL-ENAC/co2-calculator/commit/8f4e7b5f9ee32e14ecc17a8a808fa1f93d41395f))
* remove unit manipulation (will be done in backend) ([44a0012](https://github.com/EPFL-ENAC/co2-calculator/commit/44a00124111fb519ae5643542ce518b932a27036))
* remove useless imports ([580b604](https://github.com/EPFL-ENAC/co2-calculator/commit/580b604e8c83e6133953ab9bbad0f450e142078c))
* remove uv sync at root ([3992fd1](https://github.com/EPFL-ENAC/co2-calculator/commit/3992fd1efbbcbd85338a059972d0548c31e2898c))
* removing css duplacate ([8964ec9](https://github.com/EPFL-ENAC/co2-calculator/commit/8964ec98204e845a652bba5f1a37b193a3032cfd))
* role name correction ([c511371](https://github.com/EPFL-ENAC/co2-calculator/commit/c511371dc9b1b9a366ac59e188012fdf23ac09fb))
* simplify role mapping on units ([92a6aba](https://github.com/EPFL-ENAC/co2-calculator/commit/92a6abaebf7bf40d7b49ba84f87b8ef4f3aa304d))
* simplify selection ([3760493](https://github.com/EPFL-ENAC/co2-calculator/commit/3760493cb6a7dc023f8918fccc8281cb5e555a66))
* solving console error ([0796a00](https://github.com/EPFL-ENAC/co2-calculator/commit/0796a0063dc02ee8326a59f23a04c09eb1b98d2e))
* tiny css variable error ([5101b91](https://github.com/EPFL-ENAC/co2-calculator/commit/5101b91ee0ec37cab3d4d44f6eb00acb96c3cbdd))
* use grid to timeline ([ef41399](https://github.com/EPFL-ENAC/co2-calculator/commit/ef41399be3b1bd8943c37123e3ebfcd58ca61d98))
* use parent/child for route + sevral small fixes ([1cef071](https://github.com/EPFL-ENAC/co2-calculator/commit/1cef071a54734c524237176c83f0d5f03fe462ab))
* use pinia persistant state instead of cookies ([a9414e6](https://github.com/EPFL-ENAC/co2-calculator/commit/a9414e60b98d2770b878750f2f0b82729e8534b3))
