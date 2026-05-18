# [0.10.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.9.0...v0.10.0) (2026-05-18)


### Bug Fixes

* **#1167:** add min_year 2023 and ceiling to be current year ([ab1e5fe](https://github.com/EPFL-ENAC/co2-calculator/commit/ab1e5fe5bea60aa3c6a46f1152e419eff4f4bb66)), closes [#1167](https://github.com/EPFL-ENAC/co2-calculator/issues/1167)
* **#310a:** poller auto-recovers stuck RUNNING jobs (kube safety net) ([21d39ab](https://github.com/EPFL-ENAC/co2-calculator/commit/21d39ab81541fc5655948a22199342c5048b4a40)), closes [#310a](https://github.com/EPFL-ENAC/co2-calculator/issues/310a)
* **#310b:** add REFERENCE_DATA to target_type_enum + endpoint test ([114cf57](https://github.com/EPFL-ENAC/co2-calculator/commit/114cf57af0cca1206604de1c2c4b6a170bd5aaa0)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310b:** address Copilot review — critical fixes + regression tests ([6b40afa](https://github.com/EPFL-ENAC/co2-calculator/commit/6b40afab235cad03384185d15bfbb4de5e9a9ea9))
* **#310b:** early-exit recalc on empty entries + tracer logs ([3486b17](https://github.com/EPFL-ENAC/co2-calculator/commit/3486b17680b7e8d85bfa145fcde3fc144c4ac6ec)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310b:** fan out recalc for multi-type factor uploads ([2f2fe6d](https://github.com/EPFL-ENAC/co2-calculator/commit/2f2fe6d7dbab887e2870bb1ac434f6be3bbc08f7)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310b:** hand async task fns to BackgroundTasks, drop sync wrappers ([ef0d95f](https://github.com/EPFL-ENAC/co2-calculator/commit/ef0d95f2cfb2e1adc0af42eded205ff55c9024f4)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310b:** hold strong refs to fire-and-forget recalc tasks ([a4c9e6b](https://github.com/EPFL-ENAC/co2-calculator/commit/a4c9e6bc0c160f342e9f11e0a24458ec03cd0acc)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310b:** stale-factor query handles multi-type FACTORS jobs ([71c2ef7](https://github.com/EPFL-ENAC/co2-calculator/commit/71c2ef7fc150260aacd0f6f90efe488fe3e708b5)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b) [#976](https://github.com/EPFL-ENAC/co2-calculator/issues/976)
* **#310b:** trace recalc task awaits + log cancellations + harden poller ([463c524](https://github.com/EPFL-ENAC/co2-calculator/commit/463c52495e0ce78a2b0612047f611b87ee5887dc)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310c:** address Copilot review on observability columns ([e8c3413](https://github.com/EPFL-ENAC/co2-calculator/commit/e8c341351c0318531c8a01970938466871c2ea2d)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** address Copilot review on runner ([ef393e7](https://github.com/EPFL-ENAC/co2-calculator/commit/ef393e782a6f37e69d3fb8cab78c7cb8c5fcda85)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** align pipeline response schema with documented columns ([a15de23](https://github.com/EPFL-ENAC/co2-calculator/commit/a15de23099728eb7680e011efb41fe3b6c51825a)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c) [#1026](https://github.com/EPFL-ENAC/co2-calculator/issues/1026)
* **#310c:** defer provider FINISHED writes to runner (defer_finalize) ([ae629cb](https://github.com/EPFL-ENAC/co2-calculator/commit/ae629cbb3052ab03e3fe21af7b55b7f4b3315e4d)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c) [#1050](https://github.com/EPFL-ENAC/co2-calculator/issues/1050) [#1026](https://github.com/EPFL-ENAC/co2-calculator/issues/1026)
* **#310c:** gate /factors/stale on backoffice.data_management.view ([6d3d963](https://github.com/EPFL-ENAC/co2-calculator/commit/6d3d96383d2b32b608f4704340e3abd54794017a)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** replace bandit B101 assert with explicit narrowing ([05d0ba1](https://github.com/EPFL-ENAC/co2-calculator/commit/05d0ba1039ebd2a8297c8bb5038f62be3772b36b)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** single-parent alembic revision after dev linearised ([0f589de](https://github.com/EPFL-ENAC/co2-calculator/commit/0f589dedfcc0c8c3c262d11497220c9df5615484)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** snapshot+restore in registry test fixture ([e022b40](https://github.com/EPFL-ENAC/co2-calculator/commit/e022b4078b5f2de347098e4e1625c4173c195583)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310d:** address Copilot review on batch rematch ([00c4b2f](https://github.com/EPFL-ENAC/co2-calculator/commit/00c4b2f1b2a70cf4be72d1df864e42b55ec9475c)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** bot-review polish — a11y on badges, timestamps, plan alignment ([b801ac5](https://github.com/EPFL-ENAC/co2-calculator/commit/b801ac565aac5c1fa5378850a5fd7d4d5cf39af4)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1059](https://github.com/EPFL-ENAC/co2-calculator/issues/1059) [#1059](https://github.com/EPFL-ENAC/co2-calculator/issues/1059)
* **#310d:** chain_job dedup observability + collapse defensive -1 to None ([ac719eb](https://github.com/EPFL-ENAC/co2-calculator/commit/ac719eb4867679402adec3cc826484f84f2307f1)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1053](https://github.com/EPFL-ENAC/co2-calculator/issues/1053)
* **#310d:** chain_job(dedup_active=True) refuses NULL scope keys ([80ea19e](https://github.com/EPFL-ENAC/co2-calculator/commit/80ea19ef6a6e4ec7dd48c6bb1e9fa3c9b6cc1a1f)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1053](https://github.com/EPFL-ENAC/co2-calculator/issues/1053)
* **#310d:** drop dead-code orphans left by helper revert ([58c663f](https://github.com/EPFL-ENAC/co2-calculator/commit/58c663fbc15f377ca6d1cd92401ad3215a28e6f8)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** integration-sweep findings on chain_job dedup + tests ([6dc68b3](https://github.com/EPFL-ENAC/co2-calculator/commit/6dc68b3fb7f5dacbb7fb1d2f59babe4a67e9be0f)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** make BULK_PATH_PURE_ASYNC live-toggleable for emergency rollback ([932b0ad](https://github.com/EPFL-ENAC/co2-calculator/commit/932b0ad90b551d720bb57f0c304c25a9333d4583)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1053](https://github.com/EPFL-ENAC/co2-calculator/issues/1053)
* **#310d:** mypy — rename per-entry kind_field to dodge scope collision ([1e4c8f8](https://github.com/EPFL-ENAC/co2-calculator/commit/1e4c8f8520598fdd4a99f43c044b46b3d49210f3)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** narrow handler.kind_field via local var, drop assert ([88c72ec](https://github.com/EPFL-ENAC/co2-calculator/commit/88c72eccba48efc072485f71749dc66543d906e7)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** populate_existing on SSE poll + docstring tuple ([acd6f5b](https://github.com/EPFL-ENAC/co2-calculator/commit/acd6f5b609a52a211e8b284849fd1e9a09dc8810)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1052](https://github.com/EPFL-ENAC/co2-calculator/issues/1052)
* **#310d:** register aggregation handler at bootstrap + hide recalc button on incomplete modules ([e3d5faa](https://github.com/EPFL-ENAC/co2-calculator/commit/e3d5faa59cf1304cb8a3771c0ec0eb83cc4c8409)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1049](https://github.com/EPFL-ENAC/co2-calculator/issues/1049)
* **#310d:** SSE composable — race-check + api client + drop dead reconnect ([f390ed4](https://github.com/EPFL-ENAC/co2-calculator/commit/f390ed4ed4b0b81921fddd78d561d5ed8f088fb0)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1054](https://github.com/EPFL-ENAC/co2-calculator/issues/1054)
* **1116:** correct centre financier instead of IN_Centre Financier ([7c9550b](https://github.com/EPFL-ENAC/co2-calculator/commit/7c9550b5a47fe97e3ef0637239db776754f33657))
* **310:** _check_job_scope skips module check when no institutional_id ([a964759](https://github.com/EPFL-ENAC/co2-calculator/commit/a964759b28931c2bf2ff58c5ca7f7157f80f4478)), closes [#459](https://github.com/EPFL-ENAC/co2-calculator/issues/459)
* **310:** a11y — pipeline diagnostic accessible on focus [F-C1] ([6274311](https://github.com/EPFL-ENAC/co2-calculator/commit/6274311cbc9dfce0561f1d0f4b50babf5e9a9ff7)), closes [#1059](https://github.com/EPFL-ENAC/co2-calculator/issues/1059)
* **310:** atomic CAS on FINISHED job-write [B-C1] ([ecf4015](https://github.com/EPFL-ENAC/co2-calculator/commit/ecf4015f7d1880bf7451c61e30dd326523b04345))
* **310:** bot-triage round on PR [#1079](https://github.com/EPFL-ENAC/co2-calculator/issues/1079) — 3 critical, 1 perf, 2 docs/maint ([beb2b8b](https://github.com/EPFL-ENAC/co2-calculator/commit/beb2b8b48aab1eea7e400f385af24fb3d75b5c07)), closes [#459](https://github.com/EPFL-ENAC/co2-calculator/issues/459) [#1077](https://github.com/EPFL-ENAC/co2-calculator/issues/1077) [#1074](https://github.com/EPFL-ENAC/co2-calculator/issues/1074) [#1075](https://github.com/EPFL-ENAC/co2-calculator/issues/1075)
* **310:** bot-triage round on Unit 1 — commit data_session, tighten contracts ([8cc39c7](https://github.com/EPFL-ENAC/co2-calculator/commit/8cc39c73a3bed6dca61acf8cd72d02f6ddfc2480)), closes [#1083](https://github.com/EPFL-ENAC/co2-calculator/issues/1083)
* **310:** drop duplicate v1/ prefix on active-pipelines call ([eac6ee6](https://github.com/EPFL-ENAC/co2-calculator/commit/eac6ee6d0620a07fb49cb3abbd78451ac9f084e8))
* **310:** emission_recalc chains aggregation on WARNING [B-C2] ([cedc806](https://github.com/EPFL-ENAC/co2-calculator/commit/cedc80683b9f7de26cc59eba33c3ced0bb4bbb69))
* **310:** heartbeat failure aborts handler before preemption window [B-H3] ([7cdb2b7](https://github.com/EPFL-ENAC/co2-calculator/commit/7cdb2b7c08aac0ba6d6b6b2c641b42f981099951))
* **310:** is_current index discriminates job_type + claim logging [M-H2 + A-M1] ([2e1b818](https://github.com/EPFL-ENAC/co2-calculator/commit/2e1b81860688c4e5fb1b3d3a1508d453f8b92342))
* **310:** post-/review fixes — foundation demote, per-module deny test, doc accuracy ([72c97e9](https://github.com/EPFL-ENAC/co2-calculator/commit/72c97e9515709afcf43de09d60193e0c8ee4f755)), closes [#1079](https://github.com/EPFL-ENAC/co2-calculator/issues/1079)
* **310:** preserve kg_co2eq override on async path [B-H1] ([e679df5](https://github.com/EPFL-ENAC/co2-calculator/commit/e679df52db1c2835a3f58b2d8f1e71967f6254c8))
* **310:** preserve kg_co2eq=0/distance_km=0 overrides on async path ([8858221](https://github.com/EPFL-ENAC/co2-calculator/commit/885822188218a31d36a55afb6de4d296d3326678))
* **310:** reorder factors before data on data-management page ([780773a](https://github.com/EPFL-ENAC/co2-calculator/commit/780773a86f58b9ba13c8afaf7a498e9dbf52c50d))
* **310:** seed provider bypasses BULK_PATH_PURE_ASYNC gate [B-H2] ([da0da11](https://github.com/EPFL-ENAC/co2-calculator/commit/da0da11b1bacfc5297f9fb87dbfb321d4ad8dae7))
* **310:** SSE session lifetime + disconnect detection + tenant scope ([206d9f4](https://github.com/EPFL-ENAC/co2-calculator/commit/206d9f48712028a80176aa7d971c042b82c7caef)), closes [#459](https://github.com/EPFL-ENAC/co2-calculator/issues/459)
* **310:** unblock CI on feat/310/dev — format, dedup_config test, bandit B608, mypy ([7399d4b](https://github.com/EPFL-ENAC/co2-calculator/commit/7399d4b07d0682649e1e5a99f8257da59fa32ce8)), closes [#1079](https://github.com/EPFL-ENAC/co2-calculator/issues/1079) [#1070](https://github.com/EPFL-ENAC/co2-calculator/issues/1070)
* **310:** unstick the two integration tests broken by post-merge wiring ([6e4f148](https://github.com/EPFL-ENAC/co2-calculator/commit/6e4f148f4ce7ec3568a04c8dbec59f81b407fdd4))
* **310:** validate job_type matches dedup_config + narrow IntegrityError catch ([534f866](https://github.com/EPFL-ENAC/co2-calculator/commit/534f86675376d572ea5ec29e5e273acfd1669b62))
* **344:** correct format for sentry.ts ([84c8d94](https://github.com/EPFL-ENAC/co2-calculator/commit/84c8d94940efe1c3f55fa7acd6f973863e9ad9a3))
* **344:** write injectEnv.js to /tmp; nginx aliases /injectEnv.js to it ([8778dbd](https://github.com/EPFL-ENAC/co2-calculator/commit/8778dbd44cdd86898b476ef74f1f407c04ccfa70))
* **741:** accept CSV-or-API success for hasApi submodules ([d64f4a4](https://github.com/EPFL-ENAC/co2-calculator/commit/d64f4a4111cc3f709874c4dca884e7579f8ff782))
* **741:** persist reference upload status across submodule re-mounts ([db870aa](https://github.com/EPFL-ENAC/co2-calculator/commit/db870aabcde01f4d101872bf09c04e3d3d2853ff))
* **949:** retry POST/PATCH on 401 + bump session lifetimes + expiry toast ([e6ccc75](https://github.com/EPFL-ENAC/co2-calculator/commit/e6ccc75869c61414ec08972d2d54b95c6971dde5)), closes [#949](https://github.com/EPFL-ENAC/co2-calculator/issues/949)
* **993:** high level audit fail for frontend ([3ee56b6](https://github.com/EPFL-ENAC/co2-calculator/commit/3ee56b62dbb02fb461601f49cf4721d5d9683d79))
* added check for max of both active and stanby usages [#908](https://github.com/EPFL-ENAC/co2-calculator/issues/908) ([395ea06](https://github.com/EPFL-ENAC/co2-calculator/commit/395ea069bc6d832d3be7bccd6c969fa9b8b73126))
* added fr translations for equipment module [#906](https://github.com/EPFL-ENAC/co2-calculator/issues/906) ([42f7a4e](https://github.com/EPFL-ENAC/co2-calculator/commit/42f7a4e44dad67632dad90e3c2688804c4618c2c))
* added required travel fields [#919](https://github.com/EPFL-ENAC/co2-calculator/issues/919), simplified search location ui [#942](https://github.com/EPFL-ENAC/co2-calculator/issues/942) ([4ce88f6](https://github.com/EPFL-ENAC/co2-calculator/commit/4ce88f66b75b696115630a3639e5778b02d6aece))
* added results subtext for facilities [#889](https://github.com/EPFL-ENAC/co2-calculator/issues/889) ([47b6826](https://github.com/EPFL-ENAC/co2-calculator/commit/47b682692ea1575318c0055d3cf4b56a9e497bd3))
* address copilot review feedback on PR [#1168](https://github.com/EPFL-ENAC/co2-calculator/issues/1168) ([e953a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/e953a4b1c8e2e4d48fc90243390e0d46ea9f67d8))
* **alembic:** merge heads after dev integration ([824079c](https://github.com/EPFL-ENAC/co2-calculator/commit/824079caf75c9cb3acad7e6543c90aeee950cc32)), closes [#1064](https://github.com/EPFL-ENAC/co2-calculator/issues/1064)
* **alembic:** repair feat/1124 migration breakage + add smoke test ([383f237](https://github.com/EPFL-ENAC/co2-calculator/commit/383f237c02ab09a993a80e4ad95329800c0a18c3))
* backend format ([25492d4](https://github.com/EPFL-ENAC/co2-calculator/commit/25492d42a7ee784688c341d724dbec3fb3fa4160))
* case of 401 and it is a refresh request ([8a2b784](https://github.com/EPFL-ENAC/co2-calculator/commit/8a2b78495886a652bf54f3f84facf5c67e050633))
* code review ([e348437](https://github.com/EPFL-ENAC/co2-calculator/commit/e3484376a3cb9abbe5773f2c767e4dee133d8003))
* code review ([741a18e](https://github.com/EPFL-ENAC/co2-calculator/commit/741a18e2874a8e63160adba967444ae8faf6643a))
* consistent with page info ([bb552b3](https://github.com/EPFL-ENAC/co2-calculator/commit/bb552b38835cfc60586459f629c2eb86eea5c532))
* correct format ([ffb23ff](https://github.com/EPFL-ENAC/co2-calculator/commit/ffb23ff78b08a0120b3d2e45291e7e0d29c2c893))
* corrected alembic down version because of merge conflict ([244c221](https://github.com/EPFL-ENAC/co2-calculator/commit/244c221c02490f17435a270a773734ccf7464be9))
* **data-entry:** address PR review follow-ups ([6becce4](https://github.com/EPFL-ENAC/co2-calculator/commit/6becce45944f8bac11a48ad6796a21853d188464))
* **data-entry:** apply PR [#988](https://github.com/EPFL-ENAC/co2-calculator/issues/988) bot-review triage outcomes ([1648da6](https://github.com/EPFL-ENAC/co2-calculator/commit/1648da6e62d95d74f8b33cc09b34148af51c8c7f)), closes [#641](https://github.com/EPFL-ENAC/co2-calculator/issues/641) [#640](https://github.com/EPFL-ENAC/co2-calculator/issues/640)
* **data-entry:** stop persisting computed fields to DataEntry.data ([520b978](https://github.com/EPFL-ENAC/co2-calculator/commit/520b97858cdf7c7f7d7af583413b6bcb0859e264))
* distinguished missing values from 0s [#965](https://github.com/EPFL-ENAC/co2-calculator/issues/965) ([84146f0](https://github.com/EPFL-ENAC/co2-calculator/commit/84146f009478d8532cbb648f9f3943db998cfd9c))
* **format:** correct format for frontend ([8910df2](https://github.com/EPFL-ENAC/co2-calculator/commit/8910df2d4ed174275f877af8333f91d204820486))
* **frontend:** make year required in InitiateSyncParams ([aa1f679](https://github.com/EPFL-ENAC/co2-calculator/commit/aa1f679f632fae42a5494133744e0d6754f7cdcb))
* **ingestion:** align row-level year guard with setup-time falsy check ([10c991c](https://github.com/EPFL-ENAC/co2-calculator/commit/10c991c2215d5d6256badc116d90990f5b216bff))
* **ingestion:** require year for MODULE_UNIT_SPECIFIC CSV uploads ([210c4e3](https://github.com/EPFL-ENAC/co2-calculator/commit/210c4e3dc133bb87990acba4b42a37c682011eb6))
* **perf:** disable production sourcemaps to unbloat JS bundles ([971f3e2](https://github.com/EPFL-ENAC/co2-calculator/commit/971f3e2bee794befe223d6bf3085d68bd0314031))
* **perf:** drop unused ctx param from quasar config callback ([e76c376](https://github.com/EPFL-ENAC/co2-calculator/commit/e76c3767f38ccfc560ba969196b8f4233a6eb8ca))
* replaced user count (int) by fte count (float) in external ai [#900](https://github.com/EPFL-ENAC/co2-calculator/issues/900) ([ec6bda5](https://github.com/EPFL-ENAC/co2-calculator/commit/ec6bda5a10108ba11b9c9adef76b5286f63d4944))
* translation correction ([5db7d67](https://github.com/EPFL-ENAC/co2-calculator/commit/5db7d67cd57a60034cc040bcf65b53d2f60e12b3))
* **travel-api:** drop unknown_unit sentinel + use IN_Centre financier ([9b7f38e](https://github.com/EPFL-ENAC/co2-calculator/commit/9b7f38e72ee954a120de8f03fc03c3d957f52633))


### Features

* **#310b:** factor pipeline + unit sync tracking ([723060a](https://github.com/EPFL-ENAC/co2-calculator/commit/723060ad8a01499e33905703ff7476700cc3c5b3)), closes [#310b](https://github.com/EPFL-ENAC/co2-calculator/issues/310b)
* **#310c:** add GET /sync/pipelines/{id} endpoint ([e1f4b25](https://github.com/EPFL-ENAC/co2-calculator/commit/e1f4b2574bcfe55db7ec841d648aac3ef034063f)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** add handler registry scaffolding ([f37b984](https://github.com/EPFL-ENAC/co2-calculator/commit/f37b984091c2a09335a0de89baeef615aec4358d)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** add run_job runner + chain_job + heartbeat ([63c77ea](https://github.com/EPFL-ENAC/co2-calculator/commit/63c77ea17eba33ada07da805948ce2777c6a0afa)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c) [#1020](https://github.com/EPFL-ENAC/co2-calculator/issues/1020) [#2](https://github.com/EPFL-ENAC/co2-calculator/issues/2)
* **#310c:** add started_at/finished_at observability columns ([ff0d6d5](https://github.com/EPFL-ENAC/co2-calculator/commit/ff0d6d55a57d6e782cca21624cb3c2526284d7a5)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** register emission_recalc / module_emission_recalc / unit_sync handlers ([b4c8830](https://github.com/EPFL-ENAC/co2-calculator/commit/b4c88306f22c33eaab1b21fbee179386af928a3e)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c) [#2](https://github.com/EPFL-ENAC/co2-calculator/issues/2)
* **#310c:** runner cutover — endpoint+poller dispatch via run_job (Tier-2 PR [#3](https://github.com/EPFL-ENAC/co2-calculator/issues/3)) ([5d8187a](https://github.com/EPFL-ENAC/co2-calculator/commit/5d8187a11f247545ef943ce01ce0b1f0ab55d559)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310c:** validate handler signature at register-time ([f4c7583](https://github.com/EPFL-ENAC/co2-calculator/commit/f4c758333f740a9eb2be9f60947bba3c644dbc0d)), closes [#310c](https://github.com/EPFL-ENAC/co2-calculator/issues/310c)
* **#310d:** add BULK_PATH_PURE_ASYNC feature flag ([90f7ef2](https://github.com/EPFL-ENAC/co2-calculator/commit/90f7ef2da296a812d0ec13cbbd33c6e847802c5b)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5)
* **#310d:** aggregation handler + dedup-active partial unique index ([1d909da](https://github.com/EPFL-ENAC/co2-calculator/commit/1d909da1c640d6c1bf50f06545bad36cdc9cd788)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#4](https://github.com/EPFL-ENAC/co2-calculator/issues/4) [#1048](https://github.com/EPFL-ENAC/co2-calculator/issues/1048) [#1048](https://github.com/EPFL-ENAC/co2-calculator/issues/1048)
* **#310d:** back-office Recalculating badge + current_pipeline_id on recalc-status ([348ef94](https://github.com/EPFL-ENAC/co2-calculator/commit/348ef94aa54995c1195319078f7c61f1752f6c87)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1054](https://github.com/EPFL-ENAC/co2-calculator/issues/1054) [#1053](https://github.com/EPFL-ENAC/co2-calculator/issues/1053)
* **#310d:** BaseCSVProvider — gate inline emission + stats writes on flag ([a443cf7](https://github.com/EPFL-ENAC/co2-calculator/commit/a443cf720b94c0b013ea53f105d8a9a92b90c1cd)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5)
* **#310d:** chain_job dedup_active=True via uq_aggregation_active ([167a1c1](https://github.com/EPFL-ENAC/co2-calculator/commit/167a1c1d53783e358fe62c976867f424565c0b83)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5) [#1049](https://github.com/EPFL-ENAC/co2-calculator/issues/1049)
* **#310d:** contextual recalc button + pipeline diagnostic tooltip ([cc3f097](https://github.com/EPFL-ENAC/co2-calculator/commit/cc3f0971e5cd1205c271f989585b77de0ea305cd)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1054](https://github.com/EPFL-ENAC/co2-calculator/issues/1054)
* **#310d:** csv_ingest / api_ingest chain emission_recalc on success ([a176629](https://github.com/EPFL-ENAC/co2-calculator/commit/a17662948f19200ec14c98c0d498ce9ce8f4dee5)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5)
* **#310d:** emission_recalc chains aggregation; workflow drops recompute_stats ([8866365](https://github.com/EPFL-ENAC/co2-calculator/commit/886636581d252762685fe9a3a3f1d14b21d84062)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5)
* **#310d:** expose current_pipeline_id on CarbonReportModuleRead ([c39b404](https://github.com/EPFL-ENAC/co2-calculator/commit/c39b4042bb2125349fcff4a0b943282d7d8562d4)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5)
* **#310d:** per-module IT matrix for Strategy B rematch + plan-doc realignment ([7a81a24](https://github.com/EPFL-ENAC/co2-calculator/commit/7a81a24752442cf47bd19d874b051441ed65fc2d)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** pipeline SSE store + composable + module current_pipeline_id ([bb3e9ac](https://github.com/EPFL-ENAC/co2-calculator/commit/bb3e9ac809eb39bf2db2005f0ae8dafbaa18fd56)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#1052](https://github.com/EPFL-ENAC/co2-calculator/issues/1052) [#1053](https://github.com/EPFL-ENAC/co2-calculator/issues/1053)
* **#310d:** pipeline SSE stream endpoint + active-pipeline repo helper ([9ee4f3f](https://github.com/EPFL-ENAC/co2-calculator/commit/9ee4f3f4594c98f29599b292fa82c926e25181a4)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** ProfessionalTravelApiProvider — gate inline emission writes ([99ff830](https://github.com/EPFL-ENAC/co2-calculator/commit/99ff83048f1ab217d63dac397f3e9805985013f1)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d) [#5](https://github.com/EPFL-ENAC/co2-calculator/issues/5)
* **310:** chain_job DedupConfig + emission_recalc dedup [[#1064](https://github.com/EPFL-ENAC/co2-calculator/issues/1064)] ([084dac0](https://github.com/EPFL-ENAC/co2-calculator/commit/084dac0db197ea32f85a32a5363c5c9d55d59526))
* **310:** remove recalc button ([81ac5d0](https://github.com/EPFL-ENAC/co2-calculator/commit/81ac5d06ae1d3db6dc9fe9a39252ddf0556589fe))
* **310:** stale-stats health endpoint [[#1063](https://github.com/EPFL-ENAC/co2-calculator/issues/1063)] ([f99a03b](https://github.com/EPFL-ENAC/co2-calculator/commit/f99a03bd3ab30304868e0e77d560aa6fedf78280)), closes [#1062](https://github.com/EPFL-ENAC/co2-calculator/issues/1062)
* **310:** unified pipelineStateStore + active-pipelines endpoint [[#1062](https://github.com/EPFL-ENAC/co2-calculator/issues/1062)] ([e3094ef](https://github.com/EPFL-ENAC/co2-calculator/commit/e3094ef6dd791bf7467e891d1483f31618179d11))
* **344:** lower lighthouse ci to 0.6 until we found out a way to have minify resource for the CI; it's not testing properly ([c0a9cb8](https://github.com/EPFL-ENAC/co2-calculator/commit/c0a9cb85131a7b273ca7c18dd234433089a13466))
* **344:** wire APP_SENTRY_DSN/ENVIRONMENT through helm + dev .env loader ([ad54312](https://github.com/EPFL-ENAC/co2-calculator/commit/ad5431240bcbb3e628d33eb79f25380e368b86c7))
* **344:** wire GlitchTip error reporting + runtime DSN injection ([d557b7e](https://github.com/EPFL-ENAC/co2-calculator/commit/d557b7e23e7ecf4af268c0e286035a3e339dc288)), closes [#1101](https://github.com/EPFL-ENAC/co2-calculator/issues/1101)
* **741:** implement reference CSV upload for locations and building rooms ([3908cdb](https://github.com/EPFL-ENAC/co2-calculator/commit/3908cdb61a7cf2a784881f0b855066e3db259281))
* **857:** finalize back-office "Open year for users" flow ([d758bca](https://github.com/EPFL-ENAC/co2-calculator/commit/d758bca0280cf49979981c1f83c868f5364660f0)), closes [#1111](https://github.com/EPFL-ENAC/co2-calculator/issues/1111)
* **979:** add rollup do avoid dedup count in reporting table api ([0a199e2](https://github.com/EPFL-ENAC/co2-calculator/commit/0a199e2c5c9a21dc802d2b760c73e1e45611a7e6))
* add layout of simulation explore page ([bee9176](https://github.com/EPFL-ENAC/co2-calculator/commit/bee9176c45a705fb067de180aea277da0b9956e9))
* add multiple patterns for colorblind mode ([73fbba7](https://github.com/EPFL-ENAC/co2-calculator/commit/73fbba737fd56d531de03dd4fa9c51df9e2f2baa))
* add natural_key to locations ([b5bd971](https://github.com/EPFL-ENAC/co2-calculator/commit/b5bd9716e4afc0e95f2ed3b6bd998a7d010a9a11))
* add PDF print of result page charts ([6a441fb](https://github.com/EPFL-ENAC/co2-calculator/commit/6a441fb5fcd6eb7b45f675f79188cf2b8113b472))
* add purchase top-class label and validation helper ([b9c860d](https://github.com/EPFL-ENAC/co2-calculator/commit/b9c860db01c6f46c35bf565e27fc33fbaffe0e7e))
* add tooltips and form info for equipment ([9f7ff20](https://github.com/EPFL-ENAC/co2-calculator/commit/9f7ff20bf5078d29af2914a880e4c1510b9e230d))
* add translation_key and fix factor i18n handling ([27bbb6f](https://github.com/EPFL-ENAC/co2-calculator/commit/27bbb6f429e614f5fbb5d77be8424c76f7d55211))
* add travel origin/destination fields to schema ([e326aaf](https://github.com/EPFL-ENAC/co2-calculator/commit/e326aaf67b1f1f04072ce7d5ccef76f5f962d77b))
* added default notification on http error, can be skipped per http error code if operation is specifically handled ([4f0940b](https://github.com/EPFL-ENAC/co2-calculator/commit/4f0940b6f09387d0e8adc3bcebdfae0fcd74dcf8))
* added index for locations keywords, search locations by iata ([e101fc2](https://github.com/EPFL-ENAC/co2-calculator/commit/e101fc2a6d20402c0fcbdd2d45655fd06fa5460b))
* added notification info on room addition [#960](https://github.com/EPFL-ENAC/co2-calculator/issues/960) ([858fc71](https://github.com/EPFL-ENAC/co2-calculator/commit/858fc7161c51191f968cddeb2d7c7de1a2592f01))
* added records per page and page count [#959](https://github.com/EPFL-ENAC/co2-calculator/issues/959) ([b91bc1c](https://github.com/EPFL-ENAC/co2-calculator/commit/b91bc1cfd8c7da35af7b72689cec85f089e12003))
* adding decals to colorblind charts ([2914dce](https://github.com/EPFL-ENAC/co2-calculator/commit/2914dcedfb82c18a3c9ecf2591844b8ea88eb62f))
* adjust commuting chart colors and remove tooltip ([33cbc64](https://github.com/EPFL-ENAC/co2-calculator/commit/33cbc64cfc2662eed86ec3a097a4cfe22ff9e69d))
* applied trigram index to locations keywords ([ed758d3](https://github.com/EPFL-ENAC/co2-calculator/commit/ed758d357e994302c7f8616375741f7e6e58a76d))
* apply default current on purchase and external cloud data entries creation ([130549e](https://github.com/EPFL-ENAC/co2-calculator/commit/130549e18cd5e221896010598d2895c8d6d99858))
* backfill carbon_project_id and fix migrations ([c38e506](https://github.com/EPFL-ENAC/co2-calculator/commit/c38e50651a5f8e7840539e2dd774386b38a8e038))
* change minimum value for ETP field ([cee40e1](https://github.com/EPFL-ENAC/co2-calculator/commit/cee40e1977b120d167b72c0fd9af24db90b18451))
* correct translation ([915b28a](https://github.com/EPFL-ENAC/co2-calculator/commit/915b28a92705bc5cacf17ac04cdc4bd72b538fd3))
* disambiguate locations by country for train module ([3e802f4](https://github.com/EPFL-ENAC/co2-calculator/commit/3e802f4858d6406ebc5b433535107bce218b7ee1))
* implement get-or-create endpoint for Simulator Explore carbon ([6ad6da1](https://github.com/EPFL-ENAC/co2-calculator/commit/6ad6da1c5cf3f1d1a6409f8f3a35342e1b01767f))
* make position feild required and repair custom error message ([9c01554](https://github.com/EPFL-ENAC/co2-calculator/commit/9c015544b686b4740752752b8b992b147315f330))
* normalize index predicates and remove dead code ([c2bed60](https://github.com/EPFL-ENAC/co2-calculator/commit/c2bed605f5231f14d440c4e87dce772939dd50f3))
* optimize locations query using trigram index ([5411485](https://github.com/EPFL-ENAC/co2-calculator/commit/54114853fd5cc099b191e1aa48ad5b4cf8dd7ae1))
* pivot CSV export to category-subcategory rows ([c25be9d](https://github.com/EPFL-ENAC/co2-calculator/commit/c25be9d370f9b05a918df6af4f98e564abb80c22))
* **purchase:** make supplier field optional ([c8f68ab](https://github.com/EPFL-ENAC/co2-calculator/commit/c8f68ab52247e4949ff6b8ef945aef4b4e199871))
* refactor chart options and tooltip handling ([ec73312](https://github.com/EPFL-ENAC/co2-calculator/commit/ec733127f463798944fc711a9eae89072d2337a3))
* refine scope labels and add scope dividers ([0704abe](https://github.com/EPFL-ENAC/co2-calculator/commit/0704abe1a86730d31284276a553418acce69998c))
* switch submodule order ([9fcb841](https://github.com/EPFL-ENAC/co2-calculator/commit/9fcb841231d8d84b66a40b4ea0a8acca615969e2))
* translate factors ([e3f681d](https://github.com/EPFL-ENAC/co2-calculator/commit/e3f681d37730b62e45985cc234a4028ea198e115))
* **travel-train:** resolve CSV station names to Location via natural_key ([b5924f6](https://github.com/EPFL-ENAC/co2-calculator/commit/b5924f68caa09e0cbaaebeee2f7e055cc71b52c7))
* update FTE chart layout and labels ([13d3ecf](https://github.com/EPFL-ENAC/co2-calculator/commit/13d3ecf223864a238ab783142d53361fa71f9474))
* use computed props for NoteDialog labels ([19243b2](https://github.com/EPFL-ENAC/co2-calculator/commit/19243b2317065b4ac864fcf6619d15a1f10bb997))
* use i18n required messages in ModuleForm ([7840e6a](https://github.com/EPFL-ENAC/co2-calculator/commit/7840e6aa40d128323d39554e96a5ba9ddac6541e))
* use process-emissions i18n keys for gases ([41d0b95](https://github.com/EPFL-ENAC/co2-calculator/commit/41d0b952da1f178bdd07c34055e2f93eb2f6a506))
* validate calendar dates in ModuleForm ([de845b6](https://github.com/EPFL-ENAC/co2-calculator/commit/de845b6f1f27839aaadbdccca568721c800bcfba))


### Performance Improvements

* **#310d:** batch rematch in EmissionRecalculationWorkflow ([7b06dfb](https://github.com/EPFL-ENAC/co2-calculator/commit/7b06dfbeb1f468a759329f0bfd82eb3d1edbf172)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
* **#310d:** bulk-fetch active pipelines to fix N+1 on carbon-report endpoint ([f68670e](https://github.com/EPFL-ENAC/co2-calculator/commit/f68670eccc2bd78a3742eca30201d169a891c69b)), closes [#1053](https://github.com/EPFL-ENAC/co2-calculator/issues/1053)
* **344:** lazy-load @sentry/vue to keep it off the critical path ([13934f7](https://github.com/EPFL-ENAC/co2-calculator/commit/13934f789f2c208323c993f78435ce0b955db177))


### Reverts

* **#310d:** drop bulk_path_pure_async() env-direct helper ([63ef8c9](https://github.com/EPFL-ENAC/co2-calculator/commit/63ef8c93e4d2a722df6de1b9936dd853e5f4c2db)), closes [#310d](https://github.com/EPFL-ENAC/co2-calculator/issues/310d)
# [0.9.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.8.1...v0.9.0) (2026-05-04)

## Key Changes

| Area                       | What changed                                                                                                                              | Consequences / Reason                                                              |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Simulation & planning      | New Simulation Explore/Plan pages, simulator integrated into workspace setup, reduction objective chart for EPFL and units                 | Enables what-if planning and visual tracking against reduction goals               |
| Job system (#310a, #780)   | Plan 310A job claiming with safety poller; cancel-job endpoint and UI for stuck ingestion jobs                                            | Prevents zombie/lost ingestion jobs and gives operators a recovery path            |
| Data ingestion             | Seed data and seed factors refactored to reuse the CSV ingestion logic; `BaseFactorCSVProvider` aligned with parent move-failure handling | Single source of truth for ingestion; less drift between seed and runtime imports  |
| Permissions & roles (#974) | Module permissions contextualized by workspace unit and scoped to unit `institutional_id`; background role sync (later simplified to refresh-triggered) | Closes cross-unit permission leaks; roles stay current without persistent SSE      |
| Module configuration (#837) | Uncertainty tag and module constants now sourced from backend config; submodule input deactivation                                       | Consolidates configuration on the backend; less front-end drift                    |
| Year-aware factors (#927)  | Year propagated to all factor lookups; `factors_map` no longer collides across years                                                      | Resolves 500 errors and silent miscalculations on multi-year selections            |
| Pagination & filtering (#757, #781) | Server-side pagination and sorting for backoffice reporting; clearable completion status filter; multi-year validation count           | Scales reporting to large datasets and clarifies multi-year completion state       |
| Reporting & breakdowns     | SQL-driven totals in IT breakdown; rollup rows excluded from aggregations; more specific emission type id; physical quantity unified as `additional_value` | Accurate aggregations without double-counting and cleaner type granularity         |
| Affiliation filter         | Replaced Faculties/Institutes filters with a single Affiliation filter                                                                    | Simpler, less confusing filter UI                                                  |
| Locations                  | Faster CSV upload for locations                                                                                                           | Reduced ingestion time on large location datasets                                  |
| Charts & UI                | Unified ECharts tooltip component; consistent module chart order/colors; room allocation ratio (#690); calculator update card             | Visual consistency and easier interpretation                                       |

---

## Bug Fixes

| Category                 | Fixes                                                                                                                                                  | Consequences / Reason                                |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| Job system / async       | Plugged `claim_job` silent-zero leak; mirrored RUNNING guard; safer mocks (`data_entry_type_id=None`); SSE endpoint path correction; UTC time comparison | Prevents lost or duplicate ingestion jobs            |
| Data management (#780, #898) | Stale props in data entry dialog; broken upload event chain; submodule config leak; module CSV upload; `ExternalAIHandlerResponse` fields optional; deletion scoped to uploaded `data_entry_type` only | Restores reliability of the upload pipeline          |
| Permissions (#974)       | Module permission checks scoped to unit `institutional_id`                                                                                             | Closes cross-unit permission bypass                  |
| Year-aware factors (#927) | Year passed to factor values endpoint to avoid multi-year 500                                                                                          | Resolves crash on multi-year reporting selections    |
| Pagination & filters (#757, #781) | Made pagination work on backoffice reporting; respect empty filter results in `_resolve_hierarchy_unit_ids`; corrected status update test; correct stats filtering | Stops empty/invalid pagination states                |
| UX & labels (#619, #853) | Better contextual dialog text; corrected upload naming without duplication; restored compute-factors button for research-facilities; changed 0/7 to 0/8 | Removes user confusion and restores expected actions |
| Display                  | Correct decimals; correct `last_update` timestamp display in backoffice reporting                                                                      | Accurate user-facing values                          |
| Roles                    | Commit after sync of user units; updated role tests; completed role change detection                                                                    | Reliable role propagation                            |

---

## Technical Improvements (Non-functional)

| Area     | Change                                                                                                                  | Consequences / Reason                                |
| -------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Backend  | Seed data and seed factors now use CSV ingestion; removed emit-per-factor logic; CodeQL findings addressed (PR #980)    | Less code duplication; reduced static-analysis debt  |
| Frontend | Unified ECharts tooltip component; chart colors and module order normalized; `make format` cleanup                       | Consistency across charts; lint/format kept clean    |
| Testing  | Tests updated for `BaseFactorCSVProvider` refactor; safer mocks for ingestion jobs; year-aware factor coverage           | Higher confidence in pipeline changes                |



### Bug Fixes

* **#310a:** address Copilot review feedback ([2841d40](https://github.com/EPFL-ENAC/co2-calculator/commit/2841d40a262e3021e4d7f18209484a6b8ad28baf)), closes [#310a](https://github.com/EPFL-ENAC/co2-calculator/issues/310a)
* **#310a:** plug claim_job silent-zero leak; mirror RUNNING guard ([b827fff](https://github.com/EPFL-ENAC/co2-calculator/commit/b827fff5698449945f51709799aeff1654699371)), closes [#310a](https://github.com/EPFL-ENAC/co2-calculator/issues/310a)
* **#780:** run make format on frontend ([ad5dc13](https://github.com/EPFL-ENAC/co2-calculator/commit/ad5dc13b09d547683f6cff77ddacc44585a155c9)), closes [#780](https://github.com/EPFL-ENAC/co2-calculator/issues/780)
* **#974:** scope module permission checks to unit institutional_id ([e97924c](https://github.com/EPFL-ENAC/co2-calculator/commit/e97924cda8f5207e88275d3d70ddd53715274d85)), closes [#974](https://github.com/EPFL-ENAC/co2-calculator/issues/974) [#974](https://github.com/EPFL-ENAC/co2-calculator/issues/974)
* **619:** add better text for contextual dialog ([b7bcce2](https://github.com/EPFL-ENAC/co2-calculator/commit/b7bcce27eec6b6185e5c9e229ef149ee201dc70d))
* **619:** correct naming without duplicating upload ([c428f0f](https://github.com/EPFL-ENAC/co2-calculator/commit/c428f0f88532a86b24ff6f3b2606e7cb52eec306))
* **619:** format frontend properly ([f2c7854](https://github.com/EPFL-ENAC/co2-calculator/commit/f2c7854934ac1a19e20ec824296c0271126fed2c))
* **619:** restore compute-factors button for research-facilities ([26011e5](https://github.com/EPFL-ENAC/co2-calculator/commit/26011e51abd551d4c00270b8f05f1cabccf12d95))
* **757:** add a way to simplify status ([1c08031](https://github.com/EPFL-ENAC/co2-calculator/commit/1c080311487c90cd7c52e51c76645647f631c234))
* **757:** correct test for status update on carbon_report ([a632e29](https://github.com/EPFL-ENAC/co2-calculator/commit/a632e29cc4aa1037e77a7c7302753d739966f0d0))
* **757:** make pagination works ([3c524d6](https://github.com/EPFL-ENAC/co2-calculator/commit/3c524d6fda20dcc6d4a55d5ca5a405d2413e32b0))
* **757:** respect empty filter results in _resolve_hierarchy_unit_ids ([fccbecc](https://github.com/EPFL-ENAC/co2-calculator/commit/fccbecc249ea3c31550610e7ba83457ef21255e0))
* **780:** make ExternalAIHandlerResponse fields optional ([03ade21](https://github.com/EPFL-ENAC/co2-calculator/commit/03ade21d6edc231a3365a0798110e4baae1e8530))
* **780:** scope deletion to uploaded data_entry_type only ([14b43d4](https://github.com/EPFL-ENAC/co2-calculator/commit/14b43d474b8c9ec990b997de27fdac62b935e4ae))
* **781:** filter properly stats ([f1acb0d](https://github.com/EPFL-ENAC/co2-calculator/commit/f1acb0d2d0a5981d3b027f23481d47ef2adeb45a))
* **853:** change 0/7 to 0/8 ([cdee1ab](https://github.com/EPFL-ENAC/co2-calculator/commit/cdee1abbf040937852c6c81908c23af698aec44c))
* **898:** correct unit test_module_unit_specific ([2dc1a72](https://github.com/EPFL-ENAC/co2-calculator/commit/2dc1a72c4a87c74480a6f54844b2ad9eeeeb00e8))
* **898:** corret module upload csv ([f14c350](https://github.com/EPFL-ENAC/co2-calculator/commit/f14c3508e26b0e04aef6e073463318f722c0cdbc))
* **927:** pass year to factor values endpoint to avoid multi-year 500 ([9471ccc](https://github.com/EPFL-ENAC/co2-calculator/commit/9471cccf69985e13581f5e5ed09a848dfb883b13))
* add BackgroundTasks to /me endpoint for async role sync ([d33f3c3](https://github.com/EPFL-ENAC/co2-calculator/commit/d33f3c3d0aec32af64388757caf48a81cc6e326d))
* add log ([6ca64f3](https://github.com/EPFL-ENAC/co2-calculator/commit/6ca64f3a42e979d4412d8b7af92550a679655c82))
* added commit after sync user units ([4b0f476](https://github.com/EPFL-ENAC/co2-calculator/commit/4b0f4767f947f1c70dc05e796569844168bf63eb))
* added tests and safe guards ([05ba090](https://github.com/EPFL-ENAC/co2-calculator/commit/05ba090896f706af5444bc002b8c7b87a3e8ee41))
* call role provider after ttl check, ensure utc times compare ([8fae164](https://github.com/EPFL-ENAC/co2-calculator/commit/8fae16440e59d33eb36458ff67605f8550d3b464))
* code review ([55f458e](https://github.com/EPFL-ENAC/co2-calculator/commit/55f458e7c448ffdd58e85dae1404d0595f88cddc))
* code review ([44abc3c](https://github.com/EPFL-ENAC/co2-calculator/commit/44abc3c9bb5cd90300624b153649cdd3a53275ed))
* code review ([cbe07fa](https://github.com/EPFL-ENAC/co2-calculator/commit/cbe07faec691e8d19a293ac28eb824717ca4892e))
* code review ([6a46913](https://github.com/EPFL-ENAC/co2-calculator/commit/6a469132aa384633ae8d77c6bead8d9e68e6d454))
* completed role change detection ([34d24df](https://github.com/EPFL-ENAC/co2-calculator/commit/34d24df03b9983bf8e40967bbf95e3d25996a8e5))
* correct decimals ([6d0dd93](https://github.com/EPFL-ENAC/co2-calculator/commit/6d0dd93513aee1b5ca7250d80bf110c2ac3dac6f))
* correct last_update timestamp display in backoffice reporting ([534a8f4](https://github.com/EPFL-ENAC/co2-calculator/commit/534a8f403b5baeaa097865b7c038076c45f0333e))
* correct SSE endpoint path to avoid double /roles prefix ([d070e70](https://github.com/EPFL-ENAC/co2-calculator/commit/d070e709fb4d9c063cd901c07b9b39e384168c41))
* **data-management #780:** add latest_api_data_job and fix job lookup ambiguity ([1b31c89](https://github.com/EPFL-ENAC/co2-calculator/commit/1b31c892494523902f6efc01d7f30fad4bd5ea0f))
* **data-management #780:** align BaseFactorCSVProvider move-failure handling with parent class ([3e4732a](https://github.com/EPFL-ENAC/co2-calculator/commit/3e4732a40ec52328c8597e0f5bda4528bf4176e2)), closes [#780](https://github.com/EPFL-ENAC/co2-calculator/issues/780)
* **data-management #780:** fix stale props in data entry dialog and broken upload event chain ([92aa3f9](https://github.com/EPFL-ENAC/co2-calculator/commit/92aa3f972a8e4f92d3097ecb7a3b2bbaa81ed337))
* **data-management #780:** surface common upload jobs and fix submodule config leak ([10b1ff8](https://github.com/EPFL-ENAC/co2-calculator/commit/10b1ff8f9402a96330be4f98b5af02df009d75d4))
* declare active_connections as global in emit_role_update_event ([42e0472](https://github.com/EPFL-ENAC/co2-calculator/commit/42e04721f2ab1e2a19b206ef7ff0eeb2367c317f))
* make format ([cf2f2b3](https://github.com/EPFL-ENAC/co2-calculator/commit/cf2f2b38e34a92e3d9d052cb75accf93b9a8e3cf))
* pass year to all factor lookups and fix factors_map year collision ([b39fec7](https://github.com/EPFL-ENAC/co2-calculator/commit/b39fec7edbf0ddf4ae6563b20f311205fd14f8e4))
* set data_entry_type_id=None on mock job to prevent MagicMock truthy evaluation ([8ab6fe9](https://github.com/EPFL-ENAC/co2-calculator/commit/8ab6fe9b7f6cde119dfd74771639d55aba545ab5))
* **tests:** update tests for BaseFactorCSVProvider refactoring ([01f08cf](https://github.com/EPFL-ENAC/co2-calculator/commit/01f08cfa22596fb3872e622505c8cf49a5580920))
* updated code after review ([2831155](https://github.com/EPFL-ENAC/co2-calculator/commit/2831155e0b2a4dc328ef531acd5aaac60f4c2f34))
* updated role tests ([b11ab4c](https://github.com/EPFL-ENAC/co2-calculator/commit/b11ab4cb7b76a6e4c0f971b12051e1275f3ac1c3))


### Features

* **#310a:** add Plan 310A job claiming and safety poller ([dd1e870](https://github.com/EPFL-ENAC/co2-calculator/commit/dd1e870eb7d9e72c0c238b37f808956814685914)), closes [#310a](https://github.com/EPFL-ENAC/co2-calculator/issues/310a)
* **690:** added room allocation ratio, with default value 1 ([af97186](https://github.com/EPFL-ENAC/co2-calculator/commit/af971862f2066e08f71528b27f17f5fe10a29ea7))
* **757:** add a way to paginate ([d2bbe30](https://github.com/EPFL-ENAC/co2-calculator/commit/d2bbe30f2a7ade6bc6f8c8b52931cc9d843d635f))
* **757:** add better pagination sort_by ([bfc7742](https://github.com/EPFL-ENAC/co2-calculator/commit/bfc7742c14b4cee8666fc536a615e6952262b771))
* **757:** make better pagination sort ([34d68b0](https://github.com/EPFL-ENAC/co2-calculator/commit/34d68b0c48d87994eb2c1274f1ef7b84cccacfc0))
* **757:** show validated year count in validation_status for multi-year selection ([d9205c3](https://github.com/EPFL-ENAC/co2-calculator/commit/d9205c3e3672d5d3c2f51caf04a8ff9c43474621))
* **781:** completion status filter — clearable dropdown, i18n, API cleanup ([5f60082](https://github.com/EPFL-ENAC/co2-calculator/commit/5f6008276af2d58f904590184079ed22656a4539))
* **837:** add a way to use constant and backend module config ([880b1ed](https://github.com/EPFL-ENAC/co2-calculator/commit/880b1edf0e2be4f7a8a2787e0b206ac350b2c076))
* **837:** add uncertainty tag from backend ([72d72ae](https://github.com/EPFL-ENAC/co2-calculator/commit/72d72ae1022178cecd74f95a35c5dbaf4f98824a))
* **840:** add new implementations-plan ([0163c0b](https://github.com/EPFL-ENAC/co2-calculator/commit/0163c0b2460621aa23f6ca8f02784dfe48052e7a))
* **898:** improve reduction objectives upload UX ([4d0ff65](https://github.com/EPFL-ENAC/co2-calculator/commit/4d0ff655a4e8800c5dec5acffda907e989d54c63))
* add 'scope' column to data_entry_emissions table ([672b3d1](https://github.com/EPFL-ENAC/co2-calculator/commit/672b3d1d550fb86c6fe8e0681167a593d4f21af2))
* add calculator update card and i18n entries ([d43e20e](https://github.com/EPFL-ENAC/co2-calculator/commit/d43e20e2a00fb27b927cfa23704690b295080342))
* add input deactivation feature for submodules ([04466d9](https://github.com/EPFL-ENAC/co2-calculator/commit/04466d92493f9d3c36e71981b2e79cf13beddf7e))
* add last_roles_sync_at timestamp field to User model ([7476b1c](https://github.com/EPFL-ENAC/co2-calculator/commit/7476b1c70aff146994689fe3c4df35b021f2b968))
* add reduction objective chart for EPFL and my unit ([92aab3a](https://github.com/EPFL-ENAC/co2-calculator/commit/92aab3a588bcf16f9d42de1000c56d05cc28151d))
* add role sync service for background role synchronization ([477a4ba](https://github.com/EPFL-ENAC/co2-calculator/commit/477a4ba07c501f17ad6032ce9a7f1dbc169ede5a))
* add role sync store with SSE connection and TTL fallback ([940609f](https://github.com/EPFL-ENAC/co2-calculator/commit/940609f42a603abba23fe4c099703a120c99e7ec))
* add Simulation Explore and Plan pages ([9451322](https://github.com/EPFL-ENAC/co2-calculator/commit/94513222d301e910709a0011983938628822f000))
* add Simulations page UI and i18n ([db4dd21](https://github.com/EPFL-ENAC/co2-calculator/commit/db4dd21e134c1b5bc396ef9971ff68bed8b0ff26))
* add simulator in workspace setup page ([a368ea0](https://github.com/EPFL-ENAC/co2-calculator/commit/a368ea0236f5008eb2a009228c2afb30834a1f5e))
* add SSE endpoint for real-time role update notifications ([46d11af](https://github.com/EPFL-ENAC/co2-calculator/commit/46d11af916e384e94d0fd45df3d8dd9568e06213))
* add unified ECharts tooltip component ([7b02eca](https://github.com/EPFL-ENAC/co2-calculator/commit/7b02eca84ad67bbbc637f35927b8fc035ef8e799))
* added min column width in module table ([961f38f](https://github.com/EPFL-ENAC/co2-calculator/commit/961f38f6b258016add6da5345e5c9abf1130f005))
* adjusted room allocation ratio column ui (width and tooltip) ([8354c91](https://github.com/EPFL-ENAC/co2-calculator/commit/8354c9140d5f57d997bbeedb6b1e7879e682dba0))
* correct chart colors ([4177879](https://github.com/EPFL-ENAC/co2-calculator/commit/417787921c4e13eda862e2443365fd40dfd5323c))
* correct module charts order ([249573f](https://github.com/EPFL-ENAC/co2-calculator/commit/249573fcda9d02d9bf9bbae7e37e53730265d08a))
* correct module charts order ([c89b9e9](https://github.com/EPFL-ENAC/co2-calculator/commit/c89b9e95f4654d02af3b92c88c5409d0c70f600b))
* corrections ([c63ea47](https://github.com/EPFL-ENAC/co2-calculator/commit/c63ea4717ee235b2bccad769dc9d3a057fe19196))
* **data-management #780:** add cancel job endpoint and UI for stuck ingestion jobs ([50443d1](https://github.com/EPFL-ENAC/co2-calculator/commit/50443d102d1adfb9f07ba753d4cf0a81e867c98f)), closes [#780](https://github.com/EPFL-ENAC/co2-calculator/issues/780)
* exclude rollup emission rows from aggregations ([b2136c3](https://github.com/EPFL-ENAC/co2-calculator/commit/b2136c38c3511829a8bb1fdafe93cacab70a5e56))
* **locations:** faster upload of csv locations ([1ffc020](https://github.com/EPFL-ENAC/co2-calculator/commit/1ffc02002f3e8d86c84b45137fd30b2a73732cf9))
* modules permissions are contextualized by workspace's unit, simplified permissions format with list of actions ([e6dcfe9](https://github.com/EPFL-ENAC/co2-calculator/commit/e6dcfe9bef663d162491a8a69728aaf650687536))
* normalize room allocation ratio ([d8d12a1](https://github.com/EPFL-ENAC/co2-calculator/commit/d8d12a16ce8df1eba540c6efd1caea460d65638a))
* pick more specific emission type id ([4d51e39](https://github.com/EPFL-ENAC/co2-calculator/commit/4d51e395ba3ad67c84be5eac9b549b5c9ac4b13c))
* refactored seed data so that it uses the csv data ingestion logic ([e866fdf](https://github.com/EPFL-ENAC/co2-calculator/commit/e866fdf68d62fdea044d775339dbf04440b240ad))
* refactored seed factors so that it uses the csv data ingestion logic ([8b2e6dd](https://github.com/EPFL-ENAC/co2-calculator/commit/8b2e6dd15c1fb0088db42156a89fd5e4602b4052))
* remove emit per factor logic ([d454f47](https://github.com/EPFL-ENAC/co2-calculator/commit/d454f47d711eb736d276685b34c2488fd90c154e))
* replace Faculties/Institutes filters with single Affiliation filter ([448fbb8](https://github.com/EPFL-ENAC/co2-calculator/commit/448fbb8d1290d0e3a6039e6b33fe1b65c1cdb963))
* send page/page_size to API backend ([7022a69](https://github.com/EPFL-ENAC/co2-calculator/commit/7022a69afdd6375dec066de9cf354dcb7a46edfd))
* simplified implementation, no SSE, roles sync triggered on refresh instead ([744330a](https://github.com/EPFL-ENAC/co2-calculator/commit/744330a40456ce09cfc2291801ad347f6cb66e90))
* trigger background role sync from /me endpoint ([6e85b7d](https://github.com/EPFL-ENAC/co2-calculator/commit/6e85b7de0cc931c90382ff286b812c09666490f7))
* unify physical quantity as additional_value ([923ed39](https://github.com/EPFL-ENAC/co2-calculator/commit/923ed396b5a36ce333bd6907e654c128118c3590))
* use external tooltip for headcount bar chart ([aea6b7b](https://github.com/EPFL-ENAC/co2-calculator/commit/aea6b7baa731758a19b4070290e154305869b947))
* use SQL totals in IT breakdown ([0492649](https://github.com/EPFL-ENAC/co2-calculator/commit/0492649907aeef48a93350097be2a30df0ad9fe5))
* wire up server-side pagination and sorting for backoffice reporting ([79a4b2a](https://github.com/EPFL-ENAC/co2-calculator/commit/79a4b2ac1258f915fa7639a055f76d5d2ce3a304))
## [0.8.1](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.7.0...v0.8.1) (2026-04-16)


### Bug Fixes

* **#384:** display reduction percentage as 0–100 in UI, store as 0–1 ([182b5e4](https://github.com/EPFL-ENAC/co2-calculator/commit/182b5e4110fff7fcffddab7f76f57088dd079191)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **243:** create carbon_report on sync accred and get page 0 of units ([f3c4494](https://github.com/EPFL-ENAC/co2-calculator/commit/f3c44942d5ac4f8e546b4536d32df7f9dc812999))
* **504:** start by using carbon_report service for list_backoffice_units ([e031a53](https://github.com/EPFL-ENAC/co2-calculator/commit/e031a53034b837cb7a00881cd5589b15e886be3c))
* **771:** replace CO2 by CO₂ ([81f8133](https://github.com/EPFL-ENAC/co2-calculator/commit/81f8133444f79af7edbde9b9cbaced4e96886f11))
* add missing valid_module_per_year.csv test fixture ([1a54948](https://github.com/EPFL-ENAC/co2-calculator/commit/1a54948b690088e959b097dedc24c93a89698707))
* **audit:** correct root package.json ([92d0749](https://github.com/EPFL-ENAC/co2-calculator/commit/92d0749ad20e6df8cab0ebe6a42ed819c48717c8))
* **backend:** prevent path traversal in file upload (CWE-22) ([d1c0219](https://github.com/EPFL-ENAC/co2-calculator/commit/d1c02199777c3e24fa2eea47e917b7a89d1863a5)), closes [#582](https://github.com/EPFL-ENAC/co2-calculator/issues/582)
* **backend:** remove duplicated  ModuleStatus ([81edf8d](https://github.com/EPFL-ENAC/co2-calculator/commit/81edf8dd83c391c2514519bd30240fa31200de89))
* **ci:** change order of cache, we want to cache browser, not deps ([3d3ca56](https://github.com/EPFL-ENAC/co2-calculator/commit/3d3ca565c63aca3cc56742e18472ad0bb8f8f7f8))
* **ci:** install ecoindex plugin at repo root for lighthouse resolution ([ea69365](https://github.com/EPFL-ENAC/co2-calculator/commit/ea693654a6f35fa157025d3be8f82d8b9bf01317))
* **ci:** remove stall --deps install in frontend test ([0c0654a](https://github.com/EPFL-ENAC/co2-calculator/commit/0c0654ac3733ad739325f28efa5ab18c5b21b401))
* code review ([5fb06a9](https://github.com/EPFL-ENAC/co2-calculator/commit/5fb06a99d3294cbde38db2151c6bdba9785af40d))
* code review ([cbf6256](https://github.com/EPFL-ENAC/co2-calculator/commit/cbf6256bc685a9bc6898de85305f334476f831e0))
* code review ([172826e](https://github.com/EPFL-ENAC/co2-calculator/commit/172826ee6b674b479e491a2998af9e7a70e2b100))
* code review ([aa7adc7](https://github.com/EPFL-ENAC/co2-calculator/commit/aa7adc79ae9179f051ada8229aed1bc308fc5184))
* code review ([0bc468f](https://github.com/EPFL-ENAC/co2-calculator/commit/0bc468ffaf2e1b71b1c9e7547c513f4d5cdffdeb))
* code review ([43c3b01](https://github.com/EPFL-ENAC/co2-calculator/commit/43c3b01693fff429e52893477fc1359633519270))
* code review ([a560a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/a560a4b7ba461de3e06def356a43e6f376df694d))
* code review ([c2c33bf](https://github.com/EPFL-ENAC/co2-calculator/commit/c2c33bfe5be365b9bce5e48395bec4b359bf354b))
* **data-management:** wrong data_entry_type for equipment common ([cfe2529](https://github.com/EPFL-ENAC/co2-calculator/commit/cfe25297997be0c6bb6fb28aa8bf1661d6544e51))
* do not include empty files ([946bb26](https://github.com/EPFL-ENAC/co2-calculator/commit/946bb26724dc0e5db8b02f7546ddafe22ed5957e))
* **docs:** correct nginx port to 8080 for unprivileged image ([1bac431](https://github.com/EPFL-ENAC/co2-calculator/commit/1bac431570778179995e6687733c6301a4a2fcb4))
* **exchange-rate:** remove pandas ([c0fabe5](https://github.com/EPFL-ENAC/co2-calculator/commit/c0fabe55d671ddf430bcd1df2b4acb9ed11aca38))
* fix faulty transations ([773bff6](https://github.com/EPFL-ENAC/co2-calculator/commit/773bff6970121c6f40d7151de99d21d53c78678a))
* **frontend:** no more audit problem ([af965b8](https://github.com/EPFL-ENAC/co2-calculator/commit/af965b85be86613bccd29689c84266ee13ed1468))
* **frontend:** prevent infinite fetch loop in data-management child components ([60c6f99](https://github.com/EPFL-ENAC/co2-calculator/commit/60c6f992cb2d864a02d12dfaca9667cbfcf01f94))
* **frontend:** run formatting ([d5da9ab](https://github.com/EPFL-ENAC/co2-calculator/commit/d5da9ab132567fb580f03b10ab11e9154389394c))
* **frontend:** sync package-lock.json ([617247e](https://github.com/EPFL-ENAC/co2-calculator/commit/617247edde5fb864bcdbb5070f2a76dd65496ca5))
* **frontend:** sync package-lock.json ([a3e91b3](https://github.com/EPFL-ENAC/co2-calculator/commit/a3e91b38e8cb3459a224a71e0a28f6977bbdfdf5))
* handle case co2 emission is null ([4c524a6](https://github.com/EPFL-ENAC/co2-calculator/commit/4c524a62f1249f59f45b67738b8881352a0e6599))
* **helm:** add private route for openshift ([a4f2c50](https://github.com/EPFL-ENAC/co2-calculator/commit/a4f2c508057af1e4f4aff6abdf01308ec64ba940))
* **lighthouse:** switch to serve -s for SPA history-mode routing ([284eb51](https://github.com/EPFL-ENAC/co2-calculator/commit/284eb5121ffcc88f8bc80702975060ffebdb052c))
* limit dcimal ([4a40e35](https://github.com/EPFL-ENAC/co2-calculator/commit/4a40e357da31c5051b86fa2c3a4613e294929ba1))
* npm audit ([d82675e](https://github.com/EPFL-ENAC/co2-calculator/commit/d82675e0124a1d89de5c44146094ce648b2b8886))
* repare poermision errors in travel module ([0151590](https://github.com/EPFL-ENAC/co2-calculator/commit/015159098cf5deec4bad26999bbb741104fbe60d))
* repare travel table in module page ([aed75e6](https://github.com/EPFL-ENAC/co2-calculator/commit/aed75e6343b2688cca62492b719e11399231eeb2))
* **travel:** repare number of trips ([9742555](https://github.com/EPFL-ENAC/co2-calculator/commit/97425555e8d5161964ebc4d2dff14f0f57f66fda))
* **unit-user-sync:** correct cf in unit-user table ([812971b](https://github.com/EPFL-ENAC/co2-calculator/commit/812971b2244e52dc7f355e8780b71aa8f745f535))
* update CO2 calculation constant for accuracy ([a5e619d](https://github.com/EPFL-ENAC/co2-calculator/commit/a5e619d31d3961f2639c92b0f41a70cef3f6f314))
* update implementation plan 310 ([d7b70e9](https://github.com/EPFL-ENAC/co2-calculator/commit/d7b70e958bb0a4aec9b891c1ab7f2c985063610b))
* **year-configuration:** fix async crash, add lifecycle & backoffice access control ([b48c32c](https://github.com/EPFL-ENAC/co2-calculator/commit/b48c32cd27ea87d9ddec303ac071779666e2ed1d)), closes [#244](https://github.com/EPFL-ENAC/co2-calculator/issues/244)


### Features

* **#384:** add frontend validation rules to reduction goal inputs ([eba7fd1](https://github.com/EPFL-ENAC/co2-calculator/commit/eba7fd1188246227d0fb3b8a7bf3849390155837)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **#384:** merge sync jobs into year-config and wire backoffice UI controls ([2152be6](https://github.com/EPFL-ENAC/co2-calculator/commit/2152be6ac6cefefd03479f409cd9beaf3c03cdd2)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384) [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **#384:** wire reduction goals and file uploads to yearConfig store ([208b688](https://github.com/EPFL-ENAC/co2-calculator/commit/208b6881a996e72ab5a20e2fff2ae60578336c36)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **176:** handle multiple factors in emission computation logic ([509e1f9](https://github.com/EPFL-ENAC/co2-calculator/commit/509e1f9ce68b918fcf71039c7a66258ea44371b7))
* **220:** implement CSV upload verification and test suite ([01e772e](https://github.com/EPFL-ENAC/co2-calculator/commit/01e772e5b7d64c76298a62ff54e2a892525e1e45))
* **264:** format frontend ([daf0d76](https://github.com/EPFL-ENAC/co2-calculator/commit/daf0d763da74d0b06152b5c34130f2208eb062b9))
* **310:** added recalculation workflow, manual trigger ([c91ae9a](https://github.com/EPFL-ENAC/co2-calculator/commit/c91ae9a22d10f9074ea241bbec9f93739521e068))
* **504:** added carbon results report endpoint and download ui ([e3cf94a](https://github.com/EPFL-ENAC/co2-calculator/commit/e3cf94a0c7e29f22caacfb3e6be513415705e614))
* **589:** added detailed report entry point ([acb6d91](https://github.com/EPFL-ENAC/co2-calculator/commit/acb6d911298e91f623c480fe8dc5775a14d63b99))
* **589:** added download detailed report from reporting page ([36c223a](https://github.com/EPFL-ENAC/co2-calculator/commit/36c223a99fb5f73d7a9b9ef3a4047517ffc5b2ca))
* **619:** add new csv provider for reduction objectives ([3fb3c3d](https://github.com/EPFL-ENAC/co2-calculator/commit/3fb3c3d2aa854245cc6e7a2bb680378096fcdda9))
* **619:** remove active/inactive banner for the year ([ba35d07](https://github.com/EPFL-ENAC/co2-calculator/commit/ba35d07c99b263f488aca79019f58259310aa448))
* **700:** added embodied energy computation ([e412a15](https://github.com/EPFL-ENAC/co2-calculator/commit/e412a15642748fc9a391b8b9ca8194b5dceda74e))
* **701:** added embodied energy results display ([446803d](https://github.com/EPFL-ENAC/co2-calculator/commit/446803dffbb31f0199543a0704570856ae754e60))
* add additional data + improving on results page ([c9c316a](https://github.com/EPFL-ENAC/co2-calculator/commit/c9c316adc54787de6b3aa093caa3b1c9b8a817b6))
* add collapsible Co2 sidebar with toggle ([a6b6870](https://github.com/EPFL-ENAC/co2-calculator/commit/a6b6870e0bdf3ccaaf1ee0acb8e230935703b026))
* add IT focus IT enhancements ([c3aa766](https://github.com/EPFL-ENAC/co2-calculator/commit/c3aa76649b2783643e5c0e3a6f49edde34e1f0d4))
* add missing data/factor upload button in backoffice front-end ([ecee760](https://github.com/EPFL-ENAC/co2-calculator/commit/ecee760d4bc6f691c6760b101720b33ffc8e158f))
* add package name to package-lock.json ([f07e432](https://github.com/EPFL-ENAC/co2-calculator/commit/f07e432666d36221ab4546d4e6f00c92a9e7f050))
* add roles panel in user management page ([ae0a631](https://github.com/EPFL-ENAC/co2-calculator/commit/ae0a631d54eaee7116edc780f587c1e070a1197e))
* add submodule tooltip ([39d34c2](https://github.com/EPFL-ENAC/co2-calculator/commit/39d34c2a6817930a7d2b82f6545a6fe791527b93))
* add year configuration and data management system ([600614e](https://github.com/EPFL-ENAC/co2-calculator/commit/600614e36b5b5a93ab19baca20462c43f74d3580))
* added computed factors, can be synced, applied to research facilities ([3e596e0](https://github.com/EPFL-ENAC/co2-calculator/commit/3e596e08ddb070c4c35ed9f1181431c32f1317f0))
* added module type prefix to file names, added embodied energy data entries to building module ([5d1d072](https://github.com/EPFL-ENAC/co2-calculator/commit/5d1d0724162f5dbe35298fd3531f7f9ca393a4db))
* added recalculation status to submodule expansion item ([e2bde45](https://github.com/EPFL-ENAC/co2-calculator/commit/e2bde45bc2c7095f1d57a9da97fef7aa0af488e6))
* added report usage endpoint ([6f9211d](https://github.com/EPFL-ENAC/co2-calculator/commit/6f9211d289b5d259f1fcbd225436c29f1fcc5e4c))
* added usage report downloaded with filters ([91ca3d2](https://github.com/EPFL-ENAC/co2-calculator/commit/91ca3d25584efe9d39a1a5404b55f0eeff7f3bf0))
* align IT focus section with module validation ([2e3a700](https://github.com/EPFL-ENAC/co2-calculator/commit/2e3a700ff199f6ed8a7623002a607a2f3de14938))
* allow excluding modules from results summary ([e50405c](https://github.com/EPFL-ENAC/co2-calculator/commit/e50405c1713cf9fb709995ce695609620df2d666))
* change module order ([3ce8dd2](https://github.com/EPFL-ENAC/co2-calculator/commit/3ce8dd2f8dab5cef5c164a2676234d1bed775c94))
* configuration page UI ([7d5d89d](https://github.com/EPFL-ENAC/co2-calculator/commit/7d5d89d36326fb9931333304cb273bdd8a90d279))
* correct module order ([f2b4e8f](https://github.com/EPFL-ENAC/co2-calculator/commit/f2b4e8f2c1871ce10d225f8b94694d09a832587f))
* **docs:** add documentation deployment to kubernetes ([a20f6d9](https://github.com/EPFL-ENAC/co2-calculator/commit/a20f6d9e7f7cb2585839e4bfbc53383f50dd469c)), closes [#95](https://github.com/EPFL-ENAC/co2-calculator/issues/95)
* enhance carbon footprint chart with tooltip information and responsive design ([6489122](https://github.com/EPFL-ENAC/co2-calculator/commit/64891227e1020a3b5df92ba90e68fa4f0dee4978))
* enhance carbon footprint charts with additional data toggle and responsive design improvements ([e761ae9](https://github.com/EPFL-ENAC/co2-calculator/commit/e761ae960ad03dad1b1e99866d01247ba12f31c5))
* **frontend:** added buttons to recompute factors of research facilities ([81bdd0d](https://github.com/EPFL-ENAC/co2-calculator/commit/81bdd0dc60cb098909101062510d528d3209f123))
* **helm:** add enable guards for docs and frontend resources ([03401d1](https://github.com/EPFL-ENAC/co2-calculator/commit/03401d1ff2e6308d222eacf7dde4f14db0b851db))
* implement focus IT section ([cd7e8a4](https://github.com/EPFL-ENAC/co2-calculator/commit/cd7e8a49a15a677bcba689717df0477c2e558abb))
* implement institutional ID filtering for travel entries ([a921a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/a921a4b634b921a610b4aff997654db1b3d63366))
* implement lazy loading for below-fold sections on ResultsPage ([e02cdb7](https://github.com/EPFL-ENAC/co2-calculator/commit/e02cdb790882b9bfbc2995519604e7bb3c22b653))
* implementation plan ([abe243b](https://github.com/EPFL-ENAC/co2-calculator/commit/abe243b954d2497e52832e046995d39bfd41979a))
* improved ui after code review ([c098f97](https://github.com/EPFL-ENAC/co2-calculator/commit/c098f977dae8489794d10e3fa73170e5e6f9b2cc))
* **lighthouse:** bypass auth guard at runtime for CI audits ([cde4f4c](https://github.com/EPFL-ENAC/co2-calculator/commit/cde4f4c1bb1854be25cccac780cf2d3b0ccaa71c)), closes [#264](https://github.com/EPFL-ENAC/co2-calculator/issues/264)
* **lighthouse:** extend bypass to all guards and audit all 24 routes ([29ce631](https://github.com/EPFL-ENAC/co2-calculator/commit/29ce63175ebbbc09ba3019a28f9811326f356f89))
* **lighthouse:** split local vs CI configs ([768f5b9](https://github.com/EPFL-ENAC/co2-calculator/commit/768f5b980c93b87eb1cdd422866c05252f1a3eab))
* **lighthouse:** update lighthouse routes ([cb483a7](https://github.com/EPFL-ENAC/co2-calculator/commit/cb483a73974cb78f20ff84c1a7313cbe2e4497e8))
* merge system and backoffice ([422692c](https://github.com/EPFL-ENAC/co2-calculator/commit/422692c1d68ece69acf3f7185192f7a3ed6af566))
* **mkdocs:** remove site_url for env-agnostic /docs deployment ([be95e56](https://github.com/EPFL-ENAC/co2-calculator/commit/be95e56f2882dbd69a7d6318ab52489e924b37fb))
* optimize for lighthouse ([2e6e99a](https://github.com/EPFL-ENAC/co2-calculator/commit/2e6e99a9ba2a552efa898665bc273c9c3dca2e21))
* optimize for lighthouse ([8de2c4b](https://github.com/EPFL-ENAC/co2-calculator/commit/8de2c4bd79cf3b199648453780994a3d9b462ec2))
* refactor ModuleConfig UI and fix controls ([9bf2ef8](https://github.com/EPFL-ENAC/co2-calculator/commit/9bf2ef84de6fc1fca2e9c5ae79b34116936be149))
* remove depreciated system pages ([4474108](https://github.com/EPFL-ENAC/co2-calculator/commit/4474108360c4059cd35a8c436ac05b6ade15b141))
* remove institutional_id digits only validation ([831e40a](https://github.com/EPFL-ENAC/co2-calculator/commit/831e40a0bf778217f4548f31c73930a7f2ff6f23))
* remove results from Lighthouse config ([de43275](https://github.com/EPFL-ENAC/co2-calculator/commit/de43275526a6b0906c2ae291dcb2d6291b55e28d))
* remove system nav and refine sidebar/header styles ([df22ff5](https://github.com/EPFL-ENAC/co2-calculator/commit/df22ff510b8a01b5f906d2df496c9efcbffce671))
* scope headcount member list to unit role for travel users ([8c78ff3](https://github.com/EPFL-ENAC/co2-calculator/commit/8c78ff385a1574eb383101de26e4767a8640f1cf))
* scope headcount members by unit and update UI ([2095688](https://github.com/EPFL-ENAC/co2-calculator/commit/20956886508f83851bfe92a6da9e418324f5944b))
* split data managemnt page ([dae5aa2](https://github.com/EPFL-ENAC/co2-calculator/commit/dae5aa2baca2b9d100d36524a037e0f117f8a22c))
* use module completeness composable and UI tweaks ([758de82](https://github.com/EPFL-ENAC/co2-calculator/commit/758de8224922534ea1f33fdcd3bbe8d1eaed85fb))
* write report files in temp dir before zipping them in the response ([4d7ad4b](https://github.com/EPFL-ENAC/co2-calculator/commit/4d7ad4b687712a2190665060f2c9767a8e4874a5))
## [0.8.1](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.7.0...v0.8.1) (2026-04-14)


### Bug Fixes

* **#384:** display reduction percentage as 0–100 in UI, store as 0–1 ([182b5e4](https://github.com/EPFL-ENAC/co2-calculator/commit/182b5e4110fff7fcffddab7f76f57088dd079191)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **243:** create carbon_report on sync accred and get page 0 of units ([f3c4494](https://github.com/EPFL-ENAC/co2-calculator/commit/f3c44942d5ac4f8e546b4536d32df7f9dc812999))
* **504:** start by using carbon_report service for list_backoffice_units ([e031a53](https://github.com/EPFL-ENAC/co2-calculator/commit/e031a53034b837cb7a00881cd5589b15e886be3c))
* **771:** replace CO2 by CO₂ ([81f8133](https://github.com/EPFL-ENAC/co2-calculator/commit/81f8133444f79af7edbde9b9cbaced4e96886f11))
* add missing valid_module_per_year.csv test fixture ([1a54948](https://github.com/EPFL-ENAC/co2-calculator/commit/1a54948b690088e959b097dedc24c93a89698707))
* **audit:** correct root package.json ([92d0749](https://github.com/EPFL-ENAC/co2-calculator/commit/92d0749ad20e6df8cab0ebe6a42ed819c48717c8))
* **backend:** prevent path traversal in file upload (CWE-22) ([d1c0219](https://github.com/EPFL-ENAC/co2-calculator/commit/d1c02199777c3e24fa2eea47e917b7a89d1863a5)), closes [#582](https://github.com/EPFL-ENAC/co2-calculator/issues/582)
* **backend:** remove duplicated  ModuleStatus ([81edf8d](https://github.com/EPFL-ENAC/co2-calculator/commit/81edf8dd83c391c2514519bd30240fa31200de89))
* **ci:** change order of cache, we want to cache browser, not deps ([3d3ca56](https://github.com/EPFL-ENAC/co2-calculator/commit/3d3ca565c63aca3cc56742e18472ad0bb8f8f7f8))
* **ci:** install ecoindex plugin at repo root for lighthouse resolution ([ea69365](https://github.com/EPFL-ENAC/co2-calculator/commit/ea693654a6f35fa157025d3be8f82d8b9bf01317))
* **ci:** remove stall --deps install in frontend test ([0c0654a](https://github.com/EPFL-ENAC/co2-calculator/commit/0c0654ac3733ad739325f28efa5ab18c5b21b401))
* code review ([5fb06a9](https://github.com/EPFL-ENAC/co2-calculator/commit/5fb06a99d3294cbde38db2151c6bdba9785af40d))
* code review ([cbf6256](https://github.com/EPFL-ENAC/co2-calculator/commit/cbf6256bc685a9bc6898de85305f334476f831e0))
* code review ([172826e](https://github.com/EPFL-ENAC/co2-calculator/commit/172826ee6b674b479e491a2998af9e7a70e2b100))
* code review ([aa7adc7](https://github.com/EPFL-ENAC/co2-calculator/commit/aa7adc79ae9179f051ada8229aed1bc308fc5184))
* code review ([0bc468f](https://github.com/EPFL-ENAC/co2-calculator/commit/0bc468ffaf2e1b71b1c9e7547c513f4d5cdffdeb))
* code review ([43c3b01](https://github.com/EPFL-ENAC/co2-calculator/commit/43c3b01693fff429e52893477fc1359633519270))
* code review ([a560a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/a560a4b7ba461de3e06def356a43e6f376df694d))
* code review ([c2c33bf](https://github.com/EPFL-ENAC/co2-calculator/commit/c2c33bfe5be365b9bce5e48395bec4b359bf354b))
* **data-management:** wrong data_entry_type for equipment common ([cfe2529](https://github.com/EPFL-ENAC/co2-calculator/commit/cfe25297997be0c6bb6fb28aa8bf1661d6544e51))
* do not include empty files ([946bb26](https://github.com/EPFL-ENAC/co2-calculator/commit/946bb26724dc0e5db8b02f7546ddafe22ed5957e))
* **docs:** correct nginx port to 8080 for unprivileged image ([1bac431](https://github.com/EPFL-ENAC/co2-calculator/commit/1bac431570778179995e6687733c6301a4a2fcb4))
* **exchange-rate:** remove pandas ([c0fabe5](https://github.com/EPFL-ENAC/co2-calculator/commit/c0fabe55d671ddf430bcd1df2b4acb9ed11aca38))
* fix faulty transations ([773bff6](https://github.com/EPFL-ENAC/co2-calculator/commit/773bff6970121c6f40d7151de99d21d53c78678a))
* **frontend:** no more audit problem ([af965b8](https://github.com/EPFL-ENAC/co2-calculator/commit/af965b85be86613bccd29689c84266ee13ed1468))
* **frontend:** prevent infinite fetch loop in data-management child components ([60c6f99](https://github.com/EPFL-ENAC/co2-calculator/commit/60c6f992cb2d864a02d12dfaca9667cbfcf01f94))
* **frontend:** run formatting ([d5da9ab](https://github.com/EPFL-ENAC/co2-calculator/commit/d5da9ab132567fb580f03b10ab11e9154389394c))
* **frontend:** sync package-lock.json ([617247e](https://github.com/EPFL-ENAC/co2-calculator/commit/617247edde5fb864bcdbb5070f2a76dd65496ca5))
* **frontend:** sync package-lock.json ([a3e91b3](https://github.com/EPFL-ENAC/co2-calculator/commit/a3e91b38e8cb3459a224a71e0a28f6977bbdfdf5))
* handle case co2 emission is null ([4c524a6](https://github.com/EPFL-ENAC/co2-calculator/commit/4c524a62f1249f59f45b67738b8881352a0e6599))
* **helm:** add private route for openshift ([a4f2c50](https://github.com/EPFL-ENAC/co2-calculator/commit/a4f2c508057af1e4f4aff6abdf01308ec64ba940))
* **lighthouse:** switch to serve -s for SPA history-mode routing ([284eb51](https://github.com/EPFL-ENAC/co2-calculator/commit/284eb5121ffcc88f8bc80702975060ffebdb052c))
* limit dcimal ([4a40e35](https://github.com/EPFL-ENAC/co2-calculator/commit/4a40e357da31c5051b86fa2c3a4613e294929ba1))
* npm audit ([d82675e](https://github.com/EPFL-ENAC/co2-calculator/commit/d82675e0124a1d89de5c44146094ce648b2b8886))
* repare travel table in module page ([aed75e6](https://github.com/EPFL-ENAC/co2-calculator/commit/aed75e6343b2688cca62492b719e11399231eeb2))
* update CO2 calculation constant for accuracy ([a5e619d](https://github.com/EPFL-ENAC/co2-calculator/commit/a5e619d31d3961f2639c92b0f41a70cef3f6f314))
* update implementation plan 310 ([d7b70e9](https://github.com/EPFL-ENAC/co2-calculator/commit/d7b70e958bb0a4aec9b891c1ab7f2c985063610b))
* **year-configuration:** fix async crash, add lifecycle & backoffice access control ([b48c32c](https://github.com/EPFL-ENAC/co2-calculator/commit/b48c32cd27ea87d9ddec303ac071779666e2ed1d)), closes [#244](https://github.com/EPFL-ENAC/co2-calculator/issues/244)


### Features

* **#384:** add frontend validation rules to reduction goal inputs ([eba7fd1](https://github.com/EPFL-ENAC/co2-calculator/commit/eba7fd1188246227d0fb3b8a7bf3849390155837)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **#384:** merge sync jobs into year-config and wire backoffice UI controls ([2152be6](https://github.com/EPFL-ENAC/co2-calculator/commit/2152be6ac6cefefd03479f409cd9beaf3c03cdd2)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384) [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **#384:** wire reduction goals and file uploads to yearConfig store ([208b688](https://github.com/EPFL-ENAC/co2-calculator/commit/208b6881a996e72ab5a20e2fff2ae60578336c36)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **176:** handle multiple factors in emission computation logic ([509e1f9](https://github.com/EPFL-ENAC/co2-calculator/commit/509e1f9ce68b918fcf71039c7a66258ea44371b7))
* **220:** implement CSV upload verification and test suite ([01e772e](https://github.com/EPFL-ENAC/co2-calculator/commit/01e772e5b7d64c76298a62ff54e2a892525e1e45))
* **264:** format frontend ([daf0d76](https://github.com/EPFL-ENAC/co2-calculator/commit/daf0d763da74d0b06152b5c34130f2208eb062b9))
* **310:** added recalculation workflow, manual trigger ([c91ae9a](https://github.com/EPFL-ENAC/co2-calculator/commit/c91ae9a22d10f9074ea241bbec9f93739521e068))
* **504:** added carbon results report endpoint and download ui ([e3cf94a](https://github.com/EPFL-ENAC/co2-calculator/commit/e3cf94a0c7e29f22caacfb3e6be513415705e614))
* **589:** added detailed report entry point ([acb6d91](https://github.com/EPFL-ENAC/co2-calculator/commit/acb6d911298e91f623c480fe8dc5775a14d63b99))
* **589:** added download detailed report from reporting page ([36c223a](https://github.com/EPFL-ENAC/co2-calculator/commit/36c223a99fb5f73d7a9b9ef3a4047517ffc5b2ca))
* **619:** remove active/inactive banner for the year ([ba35d07](https://github.com/EPFL-ENAC/co2-calculator/commit/ba35d07c99b263f488aca79019f58259310aa448))
* **700:** added embodied energy computation ([e412a15](https://github.com/EPFL-ENAC/co2-calculator/commit/e412a15642748fc9a391b8b9ca8194b5dceda74e))
* **701:** added embodied energy results display ([446803d](https://github.com/EPFL-ENAC/co2-calculator/commit/446803dffbb31f0199543a0704570856ae754e60))
* add additional data + improving on results page ([c9c316a](https://github.com/EPFL-ENAC/co2-calculator/commit/c9c316adc54787de6b3aa093caa3b1c9b8a817b6))
* add collapsible Co2 sidebar with toggle ([a6b6870](https://github.com/EPFL-ENAC/co2-calculator/commit/a6b6870e0bdf3ccaaf1ee0acb8e230935703b026))
* add IT focus IT enhancements ([c3aa766](https://github.com/EPFL-ENAC/co2-calculator/commit/c3aa76649b2783643e5c0e3a6f49edde34e1f0d4))
* add missing data/factor upload button in backoffice front-end ([ecee760](https://github.com/EPFL-ENAC/co2-calculator/commit/ecee760d4bc6f691c6760b101720b33ffc8e158f))
* add package name to package-lock.json ([f07e432](https://github.com/EPFL-ENAC/co2-calculator/commit/f07e432666d36221ab4546d4e6f00c92a9e7f050))
* add roles panel in user management page ([ae0a631](https://github.com/EPFL-ENAC/co2-calculator/commit/ae0a631d54eaee7116edc780f587c1e070a1197e))
* add year configuration and data management system ([600614e](https://github.com/EPFL-ENAC/co2-calculator/commit/600614e36b5b5a93ab19baca20462c43f74d3580))
* added computed factors, can be synced, applied to research facilities ([3e596e0](https://github.com/EPFL-ENAC/co2-calculator/commit/3e596e08ddb070c4c35ed9f1181431c32f1317f0))
* added module type prefix to file names, added embodied energy data entries to building module ([5d1d072](https://github.com/EPFL-ENAC/co2-calculator/commit/5d1d0724162f5dbe35298fd3531f7f9ca393a4db))
* added recalculation status to submodule expansion item ([e2bde45](https://github.com/EPFL-ENAC/co2-calculator/commit/e2bde45bc2c7095f1d57a9da97fef7aa0af488e6))
* added report usage endpoint ([6f9211d](https://github.com/EPFL-ENAC/co2-calculator/commit/6f9211d289b5d259f1fcbd225436c29f1fcc5e4c))
* added usage report downloaded with filters ([91ca3d2](https://github.com/EPFL-ENAC/co2-calculator/commit/91ca3d25584efe9d39a1a5404b55f0eeff7f3bf0))
* align IT focus section with module validation ([2e3a700](https://github.com/EPFL-ENAC/co2-calculator/commit/2e3a700ff199f6ed8a7623002a607a2f3de14938))
* allow excluding modules from results summary ([e50405c](https://github.com/EPFL-ENAC/co2-calculator/commit/e50405c1713cf9fb709995ce695609620df2d666))
* change module order ([3ce8dd2](https://github.com/EPFL-ENAC/co2-calculator/commit/3ce8dd2f8dab5cef5c164a2676234d1bed775c94))
* configuration page UI ([7d5d89d](https://github.com/EPFL-ENAC/co2-calculator/commit/7d5d89d36326fb9931333304cb273bdd8a90d279))
* correct module order ([f2b4e8f](https://github.com/EPFL-ENAC/co2-calculator/commit/f2b4e8f2c1871ce10d225f8b94694d09a832587f))
* **docs:** add documentation deployment to kubernetes ([a20f6d9](https://github.com/EPFL-ENAC/co2-calculator/commit/a20f6d9e7f7cb2585839e4bfbc53383f50dd469c)), closes [#95](https://github.com/EPFL-ENAC/co2-calculator/issues/95)
* enhance carbon footprint chart with tooltip information and responsive design ([6489122](https://github.com/EPFL-ENAC/co2-calculator/commit/64891227e1020a3b5df92ba90e68fa4f0dee4978))
* enhance carbon footprint charts with additional data toggle and responsive design improvements ([e761ae9](https://github.com/EPFL-ENAC/co2-calculator/commit/e761ae960ad03dad1b1e99866d01247ba12f31c5))
* **frontend:** added buttons to recompute factors of research facilities ([81bdd0d](https://github.com/EPFL-ENAC/co2-calculator/commit/81bdd0dc60cb098909101062510d528d3209f123))
* **helm:** add enable guards for docs and frontend resources ([03401d1](https://github.com/EPFL-ENAC/co2-calculator/commit/03401d1ff2e6308d222eacf7dde4f14db0b851db))
* implement focus IT section ([cd7e8a4](https://github.com/EPFL-ENAC/co2-calculator/commit/cd7e8a49a15a677bcba689717df0477c2e558abb))
* implement institutional ID filtering for travel entries ([a921a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/a921a4b634b921a610b4aff997654db1b3d63366))
* implement lazy loading for below-fold sections on ResultsPage ([e02cdb7](https://github.com/EPFL-ENAC/co2-calculator/commit/e02cdb790882b9bfbc2995519604e7bb3c22b653))
* implementation plan ([abe243b](https://github.com/EPFL-ENAC/co2-calculator/commit/abe243b954d2497e52832e046995d39bfd41979a))
* improved ui after code review ([c098f97](https://github.com/EPFL-ENAC/co2-calculator/commit/c098f977dae8489794d10e3fa73170e5e6f9b2cc))
* **lighthouse:** bypass auth guard at runtime for CI audits ([cde4f4c](https://github.com/EPFL-ENAC/co2-calculator/commit/cde4f4c1bb1854be25cccac780cf2d3b0ccaa71c)), closes [#264](https://github.com/EPFL-ENAC/co2-calculator/issues/264)
* **lighthouse:** extend bypass to all guards and audit all 24 routes ([29ce631](https://github.com/EPFL-ENAC/co2-calculator/commit/29ce63175ebbbc09ba3019a28f9811326f356f89))
* **lighthouse:** split local vs CI configs ([768f5b9](https://github.com/EPFL-ENAC/co2-calculator/commit/768f5b980c93b87eb1cdd422866c05252f1a3eab))
* **lighthouse:** update lighthouse routes ([cb483a7](https://github.com/EPFL-ENAC/co2-calculator/commit/cb483a73974cb78f20ff84c1a7313cbe2e4497e8))
* merge system and backoffice ([422692c](https://github.com/EPFL-ENAC/co2-calculator/commit/422692c1d68ece69acf3f7185192f7a3ed6af566))
* **mkdocs:** remove site_url for env-agnostic /docs deployment ([be95e56](https://github.com/EPFL-ENAC/co2-calculator/commit/be95e56f2882dbd69a7d6318ab52489e924b37fb))
* optimize for lighthouse ([2e6e99a](https://github.com/EPFL-ENAC/co2-calculator/commit/2e6e99a9ba2a552efa898665bc273c9c3dca2e21))
* optimize for lighthouse ([8de2c4b](https://github.com/EPFL-ENAC/co2-calculator/commit/8de2c4bd79cf3b199648453780994a3d9b462ec2))
* remove depreciated system pages ([4474108](https://github.com/EPFL-ENAC/co2-calculator/commit/4474108360c4059cd35a8c436ac05b6ade15b141))
* remove results from Lighthouse config ([de43275](https://github.com/EPFL-ENAC/co2-calculator/commit/de43275526a6b0906c2ae291dcb2d6291b55e28d))
* remove system nav and refine sidebar/header styles ([df22ff5](https://github.com/EPFL-ENAC/co2-calculator/commit/df22ff510b8a01b5f906d2df496c9efcbffce671))
* scope headcount member list to unit role for travel users ([8c78ff3](https://github.com/EPFL-ENAC/co2-calculator/commit/8c78ff385a1574eb383101de26e4767a8640f1cf))
* scope headcount members by unit and update UI ([2095688](https://github.com/EPFL-ENAC/co2-calculator/commit/20956886508f83851bfe92a6da9e418324f5944b))
* write report files in temp dir before zipping them in the response ([4d7ad4b](https://github.com/EPFL-ENAC/co2-calculator/commit/4d7ad4b687712a2190665060f2c9767a8e4874a5))
# [0.8.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.7.0...v0.8.0) (2026-04-14)


### Bug Fixes

* **#384:** display reduction percentage as 0–100 in UI, store as 0–1 ([182b5e4](https://github.com/EPFL-ENAC/co2-calculator/commit/182b5e4110fff7fcffddab7f76f57088dd079191)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **243:** create carbon_report on sync accred and get page 0 of units ([f3c4494](https://github.com/EPFL-ENAC/co2-calculator/commit/f3c44942d5ac4f8e546b4536d32df7f9dc812999))
* **504:** start by using carbon_report service for list_backoffice_units ([e031a53](https://github.com/EPFL-ENAC/co2-calculator/commit/e031a53034b837cb7a00881cd5589b15e886be3c))
* **771:** replace CO2 by CO₂ ([81f8133](https://github.com/EPFL-ENAC/co2-calculator/commit/81f8133444f79af7edbde9b9cbaced4e96886f11))
* add missing valid_module_per_year.csv test fixture ([1a54948](https://github.com/EPFL-ENAC/co2-calculator/commit/1a54948b690088e959b097dedc24c93a89698707))
* **audit:** correct root package.json ([92d0749](https://github.com/EPFL-ENAC/co2-calculator/commit/92d0749ad20e6df8cab0ebe6a42ed819c48717c8))
* **backend:** prevent path traversal in file upload (CWE-22) ([d1c0219](https://github.com/EPFL-ENAC/co2-calculator/commit/d1c02199777c3e24fa2eea47e917b7a89d1863a5)), closes [#582](https://github.com/EPFL-ENAC/co2-calculator/issues/582)
* **backend:** remove duplicated  ModuleStatus ([81edf8d](https://github.com/EPFL-ENAC/co2-calculator/commit/81edf8dd83c391c2514519bd30240fa31200de89))
* **ci:** change order of cache, we want to cache browser, not deps ([3d3ca56](https://github.com/EPFL-ENAC/co2-calculator/commit/3d3ca565c63aca3cc56742e18472ad0bb8f8f7f8))
* **ci:** install ecoindex plugin at repo root for lighthouse resolution ([ea69365](https://github.com/EPFL-ENAC/co2-calculator/commit/ea693654a6f35fa157025d3be8f82d8b9bf01317))
* **ci:** remove stall --deps install in frontend test ([0c0654a](https://github.com/EPFL-ENAC/co2-calculator/commit/0c0654ac3733ad739325f28efa5ab18c5b21b401))
* code review ([5fb06a9](https://github.com/EPFL-ENAC/co2-calculator/commit/5fb06a99d3294cbde38db2151c6bdba9785af40d))
* code review ([cbf6256](https://github.com/EPFL-ENAC/co2-calculator/commit/cbf6256bc685a9bc6898de85305f334476f831e0))
* code review ([172826e](https://github.com/EPFL-ENAC/co2-calculator/commit/172826ee6b674b479e491a2998af9e7a70e2b100))
* code review ([aa7adc7](https://github.com/EPFL-ENAC/co2-calculator/commit/aa7adc79ae9179f051ada8229aed1bc308fc5184))
* code review ([0bc468f](https://github.com/EPFL-ENAC/co2-calculator/commit/0bc468ffaf2e1b71b1c9e7547c513f4d5cdffdeb))
* code review ([43c3b01](https://github.com/EPFL-ENAC/co2-calculator/commit/43c3b01693fff429e52893477fc1359633519270))
* code review ([a560a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/a560a4b7ba461de3e06def356a43e6f376df694d))
* code review ([c2c33bf](https://github.com/EPFL-ENAC/co2-calculator/commit/c2c33bfe5be365b9bce5e48395bec4b359bf354b))
* do not include empty files ([946bb26](https://github.com/EPFL-ENAC/co2-calculator/commit/946bb26724dc0e5db8b02f7546ddafe22ed5957e))
* **docs:** correct nginx port to 8080 for unprivileged image ([1bac431](https://github.com/EPFL-ENAC/co2-calculator/commit/1bac431570778179995e6687733c6301a4a2fcb4))
* **exchange-rate:** remove pandas ([c0fabe5](https://github.com/EPFL-ENAC/co2-calculator/commit/c0fabe55d671ddf430bcd1df2b4acb9ed11aca38))
* fix faulty transations ([773bff6](https://github.com/EPFL-ENAC/co2-calculator/commit/773bff6970121c6f40d7151de99d21d53c78678a))
* **frontend:** no more audit problem ([af965b8](https://github.com/EPFL-ENAC/co2-calculator/commit/af965b85be86613bccd29689c84266ee13ed1468))
* **frontend:** prevent infinite fetch loop in data-management child components ([60c6f99](https://github.com/EPFL-ENAC/co2-calculator/commit/60c6f992cb2d864a02d12dfaca9667cbfcf01f94))
* **frontend:** run formatting ([d5da9ab](https://github.com/EPFL-ENAC/co2-calculator/commit/d5da9ab132567fb580f03b10ab11e9154389394c))
* **frontend:** sync package-lock.json ([617247e](https://github.com/EPFL-ENAC/co2-calculator/commit/617247edde5fb864bcdbb5070f2a76dd65496ca5))
* **frontend:** sync package-lock.json ([a3e91b3](https://github.com/EPFL-ENAC/co2-calculator/commit/a3e91b38e8cb3459a224a71e0a28f6977bbdfdf5))
* handle case co2 emission is null ([4c524a6](https://github.com/EPFL-ENAC/co2-calculator/commit/4c524a62f1249f59f45b67738b8881352a0e6599))
* **helm:** add private route for openshift ([a4f2c50](https://github.com/EPFL-ENAC/co2-calculator/commit/a4f2c508057af1e4f4aff6abdf01308ec64ba940))
* **lighthouse:** switch to serve -s for SPA history-mode routing ([284eb51](https://github.com/EPFL-ENAC/co2-calculator/commit/284eb5121ffcc88f8bc80702975060ffebdb052c))
* limit dcimal ([4a40e35](https://github.com/EPFL-ENAC/co2-calculator/commit/4a40e357da31c5051b86fa2c3a4613e294929ba1))
* npm audit ([d82675e](https://github.com/EPFL-ENAC/co2-calculator/commit/d82675e0124a1d89de5c44146094ce648b2b8886))
* update CO2 calculation constant for accuracy ([a5e619d](https://github.com/EPFL-ENAC/co2-calculator/commit/a5e619d31d3961f2639c92b0f41a70cef3f6f314))
* update implementation plan 310 ([d7b70e9](https://github.com/EPFL-ENAC/co2-calculator/commit/d7b70e958bb0a4aec9b891c1ab7f2c985063610b))
* **year-configuration:** fix async crash, add lifecycle & backoffice access control ([b48c32c](https://github.com/EPFL-ENAC/co2-calculator/commit/b48c32cd27ea87d9ddec303ac071779666e2ed1d)), closes [#244](https://github.com/EPFL-ENAC/co2-calculator/issues/244)


### Features

* **#384:** add frontend validation rules to reduction goal inputs ([eba7fd1](https://github.com/EPFL-ENAC/co2-calculator/commit/eba7fd1188246227d0fb3b8a7bf3849390155837)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **#384:** merge sync jobs into year-config and wire backoffice UI controls ([2152be6](https://github.com/EPFL-ENAC/co2-calculator/commit/2152be6ac6cefefd03479f409cd9beaf3c03cdd2)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384) [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **#384:** wire reduction goals and file uploads to yearConfig store ([208b688](https://github.com/EPFL-ENAC/co2-calculator/commit/208b6881a996e72ab5a20e2fff2ae60578336c36)), closes [#384](https://github.com/EPFL-ENAC/co2-calculator/issues/384)
* **176:** handle multiple factors in emission computation logic ([509e1f9](https://github.com/EPFL-ENAC/co2-calculator/commit/509e1f9ce68b918fcf71039c7a66258ea44371b7))
* **220:** implement CSV upload verification and test suite ([01e772e](https://github.com/EPFL-ENAC/co2-calculator/commit/01e772e5b7d64c76298a62ff54e2a892525e1e45))
* **264:** format frontend ([daf0d76](https://github.com/EPFL-ENAC/co2-calculator/commit/daf0d763da74d0b06152b5c34130f2208eb062b9))
* **310:** added recalculation workflow, manual trigger ([c91ae9a](https://github.com/EPFL-ENAC/co2-calculator/commit/c91ae9a22d10f9074ea241bbec9f93739521e068))
* **504:** added carbon results report endpoint and download ui ([e3cf94a](https://github.com/EPFL-ENAC/co2-calculator/commit/e3cf94a0c7e29f22caacfb3e6be513415705e614))
* **589:** added detailed report entry point ([acb6d91](https://github.com/EPFL-ENAC/co2-calculator/commit/acb6d911298e91f623c480fe8dc5775a14d63b99))
* **589:** added download detailed report from reporting page ([36c223a](https://github.com/EPFL-ENAC/co2-calculator/commit/36c223a99fb5f73d7a9b9ef3a4047517ffc5b2ca))
* **619:** remove active/inactive banner for the year ([ba35d07](https://github.com/EPFL-ENAC/co2-calculator/commit/ba35d07c99b263f488aca79019f58259310aa448))
* **700:** added embodied energy computation ([e412a15](https://github.com/EPFL-ENAC/co2-calculator/commit/e412a15642748fc9a391b8b9ca8194b5dceda74e))
* **701:** added embodied energy results display ([446803d](https://github.com/EPFL-ENAC/co2-calculator/commit/446803dffbb31f0199543a0704570856ae754e60))
* add additional data + improving on results page ([c9c316a](https://github.com/EPFL-ENAC/co2-calculator/commit/c9c316adc54787de6b3aa093caa3b1c9b8a817b6))
* add collapsible Co2 sidebar with toggle ([a6b6870](https://github.com/EPFL-ENAC/co2-calculator/commit/a6b6870e0bdf3ccaaf1ee0acb8e230935703b026))
* add IT focus IT enhancements ([c3aa766](https://github.com/EPFL-ENAC/co2-calculator/commit/c3aa76649b2783643e5c0e3a6f49edde34e1f0d4))
* add missing data/factor upload button in backoffice front-end ([ecee760](https://github.com/EPFL-ENAC/co2-calculator/commit/ecee760d4bc6f691c6760b101720b33ffc8e158f))
* add package name to package-lock.json ([f07e432](https://github.com/EPFL-ENAC/co2-calculator/commit/f07e432666d36221ab4546d4e6f00c92a9e7f050))
* add roles panel in user management page ([ae0a631](https://github.com/EPFL-ENAC/co2-calculator/commit/ae0a631d54eaee7116edc780f587c1e070a1197e))
* add year configuration and data management system ([600614e](https://github.com/EPFL-ENAC/co2-calculator/commit/600614e36b5b5a93ab19baca20462c43f74d3580))
* added computed factors, can be synced, applied to research facilities ([3e596e0](https://github.com/EPFL-ENAC/co2-calculator/commit/3e596e08ddb070c4c35ed9f1181431c32f1317f0))
* added module type prefix to file names, added embodied energy data entries to building module ([5d1d072](https://github.com/EPFL-ENAC/co2-calculator/commit/5d1d0724162f5dbe35298fd3531f7f9ca393a4db))
* added recalculation status to submodule expansion item ([e2bde45](https://github.com/EPFL-ENAC/co2-calculator/commit/e2bde45bc2c7095f1d57a9da97fef7aa0af488e6))
* added report usage endpoint ([6f9211d](https://github.com/EPFL-ENAC/co2-calculator/commit/6f9211d289b5d259f1fcbd225436c29f1fcc5e4c))
* added usage report downloaded with filters ([91ca3d2](https://github.com/EPFL-ENAC/co2-calculator/commit/91ca3d25584efe9d39a1a5404b55f0eeff7f3bf0))
* align IT focus section with module validation ([2e3a700](https://github.com/EPFL-ENAC/co2-calculator/commit/2e3a700ff199f6ed8a7623002a607a2f3de14938))
* allow excluding modules from results summary ([e50405c](https://github.com/EPFL-ENAC/co2-calculator/commit/e50405c1713cf9fb709995ce695609620df2d666))
* change module order ([3ce8dd2](https://github.com/EPFL-ENAC/co2-calculator/commit/3ce8dd2f8dab5cef5c164a2676234d1bed775c94))
* configuration page UI ([7d5d89d](https://github.com/EPFL-ENAC/co2-calculator/commit/7d5d89d36326fb9931333304cb273bdd8a90d279))
* correct module order ([f2b4e8f](https://github.com/EPFL-ENAC/co2-calculator/commit/f2b4e8f2c1871ce10d225f8b94694d09a832587f))
* **docs:** add documentation deployment to kubernetes ([a20f6d9](https://github.com/EPFL-ENAC/co2-calculator/commit/a20f6d9e7f7cb2585839e4bfbc53383f50dd469c)), closes [#95](https://github.com/EPFL-ENAC/co2-calculator/issues/95)
* enhance carbon footprint chart with tooltip information and responsive design ([6489122](https://github.com/EPFL-ENAC/co2-calculator/commit/64891227e1020a3b5df92ba90e68fa4f0dee4978))
* enhance carbon footprint charts with additional data toggle and responsive design improvements ([e761ae9](https://github.com/EPFL-ENAC/co2-calculator/commit/e761ae960ad03dad1b1e99866d01247ba12f31c5))
* **frontend:** added buttons to recompute factors of research facilities ([81bdd0d](https://github.com/EPFL-ENAC/co2-calculator/commit/81bdd0dc60cb098909101062510d528d3209f123))
* **helm:** add enable guards for docs and frontend resources ([03401d1](https://github.com/EPFL-ENAC/co2-calculator/commit/03401d1ff2e6308d222eacf7dde4f14db0b851db))
* implement focus IT section ([cd7e8a4](https://github.com/EPFL-ENAC/co2-calculator/commit/cd7e8a49a15a677bcba689717df0477c2e558abb))
* implement institutional ID filtering for travel entries ([a921a4b](https://github.com/EPFL-ENAC/co2-calculator/commit/a921a4b634b921a610b4aff997654db1b3d63366))
* implement lazy loading for below-fold sections on ResultsPage ([e02cdb7](https://github.com/EPFL-ENAC/co2-calculator/commit/e02cdb790882b9bfbc2995519604e7bb3c22b653))
* implementation plan ([abe243b](https://github.com/EPFL-ENAC/co2-calculator/commit/abe243b954d2497e52832e046995d39bfd41979a))
* improved ui after code review ([c098f97](https://github.com/EPFL-ENAC/co2-calculator/commit/c098f977dae8489794d10e3fa73170e5e6f9b2cc))
* **lighthouse:** bypass auth guard at runtime for CI audits ([cde4f4c](https://github.com/EPFL-ENAC/co2-calculator/commit/cde4f4c1bb1854be25cccac780cf2d3b0ccaa71c)), closes [#264](https://github.com/EPFL-ENAC/co2-calculator/issues/264)
* **lighthouse:** extend bypass to all guards and audit all 24 routes ([29ce631](https://github.com/EPFL-ENAC/co2-calculator/commit/29ce63175ebbbc09ba3019a28f9811326f356f89))
* **lighthouse:** split local vs CI configs ([768f5b9](https://github.com/EPFL-ENAC/co2-calculator/commit/768f5b980c93b87eb1cdd422866c05252f1a3eab))
* **lighthouse:** update lighthouse routes ([cb483a7](https://github.com/EPFL-ENAC/co2-calculator/commit/cb483a73974cb78f20ff84c1a7313cbe2e4497e8))
* merge system and backoffice ([422692c](https://github.com/EPFL-ENAC/co2-calculator/commit/422692c1d68ece69acf3f7185192f7a3ed6af566))
* **mkdocs:** remove site_url for env-agnostic /docs deployment ([be95e56](https://github.com/EPFL-ENAC/co2-calculator/commit/be95e56f2882dbd69a7d6318ab52489e924b37fb))
* optimize for lighthouse ([2e6e99a](https://github.com/EPFL-ENAC/co2-calculator/commit/2e6e99a9ba2a552efa898665bc273c9c3dca2e21))
* optimize for lighthouse ([8de2c4b](https://github.com/EPFL-ENAC/co2-calculator/commit/8de2c4bd79cf3b199648453780994a3d9b462ec2))
* remove depreciated system pages ([4474108](https://github.com/EPFL-ENAC/co2-calculator/commit/4474108360c4059cd35a8c436ac05b6ade15b141))
* remove results from Lighthouse config ([de43275](https://github.com/EPFL-ENAC/co2-calculator/commit/de43275526a6b0906c2ae291dcb2d6291b55e28d))
* remove system nav and refine sidebar/header styles ([df22ff5](https://github.com/EPFL-ENAC/co2-calculator/commit/df22ff510b8a01b5f906d2df496c9efcbffce671))
* scope headcount member list to unit role for travel users ([8c78ff3](https://github.com/EPFL-ENAC/co2-calculator/commit/8c78ff385a1574eb383101de26e4767a8640f1cf))
* scope headcount members by unit and update UI ([2095688](https://github.com/EPFL-ENAC/co2-calculator/commit/20956886508f83851bfe92a6da9e418324f5944b))
* write report files in temp dir before zipping them in the response ([4d7ad4b](https://github.com/EPFL-ENAC/co2-calculator/commit/4d7ad4b687712a2190665060f2c9767a8e4874a5))
# [0.7.0](https://github.com/EPFL-ENAC/co2-calculator/compare/v0.6.1...v0.7.0) (2026-03-30)

## Key Changes

| Area               | What changed                                                                                                   | Consequences / Reason                                                                    |
| ------------------ | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Reporting          | Aggregated reporting view, improved breakdowns, usage statistics, Centre-level reporting                       | Enables more granular analysis and supports higher-level organizational reporting needs  |
| Emissions coverage | Added research facilities (incl. animals, commons), improved travel and purchases, more granular building data | Expands scope to cover missing emission sources and improves accuracy of calculations    |
| Data management    | New data management interface with permissions, status tracking, source tracking                               | Introduces governance and traceability to better control data lifecycle                  |
| CSV workflows      | Delete-before-insert logic, factor override via CSV, improved upload handling                                  | Prevents duplication issues and allows controlled manual corrections of emission factors |
| Currency           | CHF/EUR support, exchange rate integration                                                                     | Aligns calculations with financial data across different currencies                      |
| Charts & UI        | More emission subcategories, improved charts, tooltips, labeling fixes                                         | Improves readability and interpretation of emissions data                                |
| Performance        | Caching for report year, backend optimizations, improved logging                                               | Reduces latency and helps diagnose issues more effectively                               |
| CI/CD & security   | Dependency updates, pipeline adjustments, security fixes                                                       | Maintains system security and ensures more reliable deployments                          |

---

## Bug Fixes

| Category           | Fixes                                                                                                | Consequences / Reason                                           |
| ------------------ | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Calculations       | Fixed incorrect emission factors (travel, purchases, buildings), corrected CO₂ overrides             | Ensures consistency and correctness of reported emissions       |
| Data handling      | Fixed API inconsistencies, data retrieval issues, factor updates                                     | Prevents data mismatches and improves reliability of data flows |
| Permissions & auth | Fixed upload permissions, Entra authentication issues, applied correct access controls               | Restores proper access control and avoids user blocking issues  |
| UX & workflows     | Fixed CSV upload flow (submit, edge cases), resolved stuck “running jobs”, improved labels and forms | Removes friction and avoids invalid or blocked user actions     |
| Frontend           | Fixed state handling, audit issues, dependency errors                                                | Reduces UI instability and unexpected behavior                  |

---

## Technical Improvements (Non-functional)

| Area     | Change                                                | Consequences / Reason                               |
| -------- | ----------------------------------------------------- | --------------------------------------------------- |
| Backend  | Refactoring, logging improvements, docker base update | Improves maintainability and debugging capabilities |
| Frontend | Audit fixes, component updates, chart improvements    | Ensures consistency and reduces technical debt      |
| Testing  | Fixed failing tests (institutional ID, data entry)    | Increases confidence in system stability            |



### Bug Fixes

* **175:** handle researchfacility_id as a string ([a4e1039](https://github.com/EPFL-ENAC/co2-calculator/commit/a4e1039a75a4c09b87b89d46119e07ce1478c10c))
* **175:** labels of column tables ([847ef84](https://github.com/EPFL-ENAC/co2-calculator/commit/847ef842302d09611cddd6185bbeaf3ddb5d3091))
* **243:** add submit for upload csv dialog ([26f2d25](https://github.com/EPFL-ENAC/co2-calculator/commit/26f2d25a61f69f88b470b35be7d8086e3192b65d))
* **243:** allow weird state of 'running jobs' staled ([d6b48f1](https://github.com/EPFL-ENAC/co2-calculator/commit/d6b48f1c34eff89ecd655b04e05e20bc19da461e))
* **243:** correct bad code for api-travel ([da8355f](https://github.com/EPFL-ENAC/co2-calculator/commit/da8355fbb29ad3c7b73f37b96ce2d1df775abbd1))
* **243:** correct permission for upload data in module specific ([bd1a65b](https://github.com/EPFL-ENAC/co2-calculator/commit/bd1a65b78f00c1bc0ba12a6e1a0ed6b25952c513))
* **243:** correct the way we retrieve data-management ([aef66bf](https://github.com/EPFL-ENAC/co2-calculator/commit/aef66bfd198635f92b852b1f9bee5dcc8f377504))
* **243:** correct travel api bad factor ([1c33117](https://github.com/EPFL-ENAC/co2-calculator/commit/1c33117fd044b9b2bf67a3e3306ce09fbb5eb56b))
* **243:** corret name for modules ([f9d1d97](https://github.com/EPFL-ENAC/co2-calculator/commit/f9d1d97d85f67ace61f885028e797604344b91ab))
* **243:** fix purchase factors update ([a510f6f](https://github.com/EPFL-ENAC/co2-calculator/commit/a510f6f63e2633a0105f4a37a0774d31cf890a1b))
* **243:** no more elec for building_rooms factors ([688f740](https://github.com/EPFL-ENAC/co2-calculator/commit/688f7407cf4ada35442f2c1eaaf7c769866757cf))
* **243:** reinstated code in taxonomies endpoint ([92ce47a](https://github.com/EPFL-ENAC/co2-calculator/commit/92ce47a451e7541606a342cd6891d270c9f8f532))
* **243:** use ref instead of reactive for events ([ae82a48](https://github.com/EPFL-ENAC/co2-calculator/commit/ae82a48f3c59e991a610e9424e9efea657868136))
* **518:** make test_data_entry pass for user_institu ([548edff](https://github.com/EPFL-ENAC/co2-calculator/commit/548edff7a7a172bced049840abf5cbc899918541))
* **518:** user_institutional_id is a str ([e2adcd1](https://github.com/EPFL-ENAC/co2-calculator/commit/e2adcd149813682c154a091816d77b207cc60996))
* added purchase categories to factors ([f3105bb](https://github.com/EPFL-ENAC/co2-calculator/commit/f3105bbe3e3e649ae837fc77eab1ae5bc70a32d1))
* **auth:** no more problem with entra ([59a53a7](https://github.com/EPFL-ENAC/co2-calculator/commit/59a53a74ef2f28daad38810831259260d615b86d))
* changed backend docker image base ([297a55b](https://github.com/EPFL-ENAC/co2-calculator/commit/297a55bb5b2f00f62095abceb87b258829db1b7b))
* changed trivy scan exit code ([eeb978e](https://github.com/EPFL-ENAC/co2-calculator/commit/eeb978e9e8cd7857d3dc0e0efed1d1f895d31353))
* **ci-cd:** remove skip flag ([ab39433](https://github.com/EPFL-ENAC/co2-calculator/commit/ab39433d99277726ca0f90a5dffd50d2d11e6b6e))
* code cleaning after review ([c7cc5d6](https://github.com/EPFL-ENAC/co2-calculator/commit/c7cc5d663cbae8c7ac105e4a26f27ba54c5bf4a2))
* **data-management:** add logs to travel-api ([c5a76a4](https://github.com/EPFL-ENAC/co2-calculator/commit/c5a76a49820d6c2f6c1e576645b17a1648c853b2))
* **deployment:** disable trivy scan ([92a087a](https://github.com/EPFL-ENAC/co2-calculator/commit/92a087a9289131e90f5453e1b920c74595071cc1))
* **deploy:** roll back ci/cd to 2.8.0 ([8742895](https://github.com/EPFL-ENAC/co2-calculator/commit/874289584edaf00dddc4ea018fd256c5b98cb7f1))
* frontend audit ([69ccfa9](https://github.com/EPFL-ENAC/co2-calculator/commit/69ccfa95086490cbcbdcb8af5febd49e54e35a65))
* **frontend-audit:** correct dependabot errors ([754b4b8](https://github.com/EPFL-ENAC/co2-calculator/commit/754b4b89ab8d8563223fb3ff9e12a40c8985eec3))
* **frontend:** audit pico ([8b7b0f6](https://github.com/EPFL-ENAC/co2-calculator/commit/8b7b0f622e231e94198bbf39c4c003824aebf92b))
* handle undefined validatedTotals in formDefaults computation ([839ddba](https://github.com/EPFL-ENAC/co2-calculator/commit/839ddbaaef00f02d9505d746c506e051f029c0d3))
* **lightouse:** run lighthouse on the frontend folder instead of root ([97ad736](https://github.com/EPFL-ENAC/co2-calculator/commit/97ad73663a4b77fc49f6c3efb843ae4a8e347879))
* **npm:** bump flatted for security reason ([5df1ca8](https://github.com/EPFL-ENAC/co2-calculator/commit/5df1ca81a96c96b24fcb6867d893332177eb77ff))
* **travel-api:** sync kg_co2eq properly (overide compute) ([f957600](https://github.com/EPFL-ENAC/co2-calculator/commit/f9576005b1ce3459cdc088ea25cc1a7983b35f7f))


### Features

* **175:** added cache for getting carbon report year ([ab249b8](https://github.com/EPFL-ENAC/co2-calculator/commit/ab249b85be4b5086990e025d5d7a754654a146ea))
* **175:** added carbon report year lookup ([b1d2e35](https://github.com/EPFL-ENAC/co2-calculator/commit/b1d2e356fc1c1609922eb1ae03c9a0bf19ba55da))
* **175:** added emissions formulas for research facilities commons and animals ([96d2d8c](https://github.com/EPFL-ENAC/co2-calculator/commit/96d2d8c2321612b4f253de8e604de1a94587d31e))
* **175:** updated formulas to use factor's year ([4e7af78](https://github.com/EPFL-ENAC/co2-calculator/commit/4e7af78f7f5cb7d4817d4572bebe1bce9686a1be))
* **175:** updated module tables according to seeded data ([f119498](https://github.com/EPFL-ENAC/co2-calculator/commit/f119498091eb0cba07f0f07dcd3224730aec4478))
* **243-data_ingestion:** add data primary_Factor_id ([411abe4](https://github.com/EPFL-ENAC/co2-calculator/commit/411abe453c85a2b8b14e0afd63aa3a3831edcd17))
* **243:** add a source to keep track of who created the darta ([e6977b5](https://github.com/EPFL-ENAC/co2-calculator/commit/e6977b5f0f59dee2e401d7380fe652928d7d5592))
* **243:** add override of factors on datamanagement ([0dd7ba4](https://github.com/EPFL-ENAC/co2-calculator/commit/0dd7ba4e56494a6cf2208e5a13c750842c8beb53))
* **243:** add stats for carbon_reports ([63a07cc](https://github.com/EPFL-ENAC/co2-calculator/commit/63a07cc561ec5513f53e18aff6444a3005a976f9))
* **243:** add travel load with emissions ([bcac014](https://github.com/EPFL-ENAC/co2-calculator/commit/bcac0146939a87ea6026a4da064ba79e01268b64))
* **243:** correct data/factor upload ([61103b5](https://github.com/EPFL-ENAC/co2-calculator/commit/61103b5338d6bf4af350e7774f104c95a5e9bdad))
* **243:** delete on insert ([a27be35](https://github.com/EPFL-ENAC/co2-calculator/commit/a27be35d6d074f3d24676dee54556329e86d9b40))
* **243:** display status of datamanagrement tab ([b55f0ca](https://github.com/EPFL-ENAC/co2-calculator/commit/b55f0caa096443366e11b763cc10243adfac4f3b))
* **243:** implement delete-before-insert pattern for CSV factor uploads ([776ad58](https://github.com/EPFL-ENAC/co2-calculator/commit/776ad580457846a5649e6eeeb5b6b81fd5a3b373))
* **402:** added currency selection for purchases (chf) and external cloud (eur) ([910b441](https://github.com/EPFL-ENAC/co2-calculator/commit/910b44129e8b8b7c16bf5290ed1b22493c6c0528))
* **700:** added workflows for carbon report module and embodied energy ([a559026](https://github.com/EPFL-ENAC/co2-calculator/commit/a5590261e71c24034ea04551e6d6b9d611f79270))
* **700:** cascade embodied data entry management ([49a1cf2](https://github.com/EPFL-ENAC/co2-calculator/commit/49a1cf297ce3c369ed8a175ea608251b0a0d6f7c))
* add CSV override for kg_co2eq in emission calculations ([704979c](https://github.com/EPFL-ENAC/co2-calculator/commit/704979c07656bd071aaefbae25368a09eb499ce7))
* add emission type breakdown info tooltips and update chart components ([9a06338](https://github.com/EPFL-ENAC/co2-calculator/commit/9a063388fc59ff45b0a9a23d6cc82b41303fb02a))
* add formDefaults support and defaultFrom field for total_fte in module configuration ([7c8f9e5](https://github.com/EPFL-ENAC/co2-calculator/commit/7c8f9e555bca051488f05fe8d8fcb7e2fe813558))
* add institutional ID uniqueness check and remove student FTE calculator ([e64023c](https://github.com/EPFL-ENAC/co2-calculator/commit/e64023cdd3e977ce1de6e437eb2be5babe45a330))
* add new subcategories in emission breakdown chart ([6cc45f1](https://github.com/EPFL-ENAC/co2-calculator/commit/6cc45f1268fff060d17460c729c88d80191a48cd))
* add usage statistics title to reporting page and update styles ([6ea780f](https://github.com/EPFL-ENAC/co2-calculator/commit/6ea780f4f296674313d4afd04b03ff757624051e))
* added direct way to get exchange rate to eur ([84cd32d](https://github.com/EPFL-ENAC/co2-calculator/commit/84cd32d9888261f8d50a7f9b3196949fd2835de1))
* added formula func for currencies ([0c2fec2](https://github.com/EPFL-ENAC/co2-calculator/commit/0c2fec24b98b308fbe204ad0d625bee9f2c583fd))
* applied research facilities permissions ([fa0da1b](https://github.com/EPFL-ENAC/co2-calculator/commit/fa0da1b3dea80f8d0732c801847afed2c8bfa364))
* **backoffice:** implement data management and granular permissions ([2114bb2](https://github.com/EPFL-ENAC/co2-calculator/commit/2114bb2f79f61c0c228d79641e7166d9dd742892)), closes [#243](https://github.com/EPFL-ENAC/co2-calculator/issues/243)
* enhance emission types and granularity for buildings and additional purchases ([1ee4dd3](https://github.com/EPFL-ENAC/co2-calculator/commit/1ee4dd35c58bbd231b77e96e602785215fcb8ee9))
* enhance reporting with additional unit status counts and module breakdown ([f7fff90](https://github.com/EPFL-ENAC/co2-calculator/commit/f7fff90c48b68d9d590ca303114ff96721666786))
* enhance reporting with aggregated results and improved data handling ([ea08c25](https://github.com/EPFL-ENAC/co2-calculator/commit/ea08c252c7bcd2733eef1034361f968a5847465e))
* implement Aggregated box section in backend's reporting tab ([14e80d4](https://github.com/EPFL-ENAC/co2-calculator/commit/14e80d4d6f76255033509ff50b1b00532253f486))
* implementation plan ([3cf80ae](https://github.com/EPFL-ENAC/co2-calculator/commit/3cf80aed253cc1210c0aaefe37ff785e27f46710))
* implementation-plan ([2ec5743](https://github.com/EPFL-ENAC/co2-calculator/commit/2ec5743e5d379fc5334252e6b6cfcfb5c11a7615))
* refactor emission breakdown interfaces and update import paths ([0b85b9b](https://github.com/EPFL-ENAC/co2-calculator/commit/0b85b9b07ddd9c24a495c529b58bee501fbed959))
* remove scope from data entry emission ([99ba01c](https://github.com/EPFL-ENAC/co2-calculator/commit/99ba01c21999beba233e819cd58cd00138ebf10d))
* **reporting:** add Centre for level 4 units ([4fd09ee](https://github.com/EPFL-ENAC/co2-calculator/commit/4fd09ee91a60bde29af151c4a144e08fae9dcc2a))
* update chart categories and keys for buildings emissions ([61841fe](https://github.com/EPFL-ENAC/co2-calculator/commit/61841fe8e0cc5bbdf78e8060db4e4e9146a7872b))
* update emission type charts with new subcategory color schemes and enhance chart options ([d097622](https://github.com/EPFL-ENAC/co2-calculator/commit/d097622dc52d93524ac173317fa363a7be31deb4))
* update GitHub button styling for better alignment ([61596b0](https://github.com/EPFL-ENAC/co2-calculator/commit/61596b04baad7ed1bf8751cd840bf8ccfaa0e5e4))


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
