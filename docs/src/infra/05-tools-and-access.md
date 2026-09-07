# Tools and Access

Every tool an operator of co2-calculator touches, what it is for, and how
a newcomer gets in. Incident procedure is in
[Operations](04-operations.md); per-environment links are there too.

## Tools

| Tool                    | Use it for                                                                                   | Where                                                                                     | Access                                                                                                                                                                                |
| ----------------------- | -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Icinga                  | External probes and the status page: http, https, api, DNS, PostgreSQL, certificate, per env | [enacitmonitoring22.epfl.ch/icingaweb2](https://enacitmonitoring22.epfl.ch/icingaweb2/)   | EPFL LDAP login. Host group `co2-calculator`. Managed by the ENAC-IT Icinga admins (DRP roster)                                                                                       |
| Grafana, per cluster    | Metrics, the "specific graphs" dashboard, alert state                                        | One instance per cluster, links in [Operations](04-operations.md#links-per-environment)   | OpenShift login, same group as the namespace                                                                                                                                          |
| Tempo                   | Traces from backend and worker                                                               | [enac-k8s-grafana.epfl.ch](https://enac-k8s-grafana.epfl.ch/), Explore, Tempo data source | ENAC-IT Grafana account; ask the ENAC-IT sysadmins                                                                                                                                    |
| OpenShift console, `oc` | Pods, logs, ExternalSecret status, rollouts                                                  | One console per cluster, links in Operations                                              | Membership of the EPFL group bound to the namespace (below); `oc login --web`                                                                                                         |
| ArgoCD                  | Sync state, diff, rollback                                                                   | One per cluster, links in Operations                                                      | OpenShift login                                                                                                                                                                       |
| GlitchTip               | Frontend JavaScript errors, with `trace_id`                                                  | [enac-it-glitchtip.epfl.ch](https://enac-it-glitchtip.epfl.ch)                            | Dedicated account, not SSO. Team credentials are in Infisical under `ENAC-IT K8S/k8s-prod/epfl-enac/glitchtip`. Details: [Frontend Error Monitoring](../frontend/error-monitoring.md) |
| Infisical               | All application secrets, all environments                                                    | [enac-it-secrets.epfl.ch](https://enac-it-secrets.epfl.ch), path `/epfl/co2-calculator`   | Invitation by the Infisical admins (DRP roster); login is a dedicated email, not SSO                                                                                                  |
| Quay                    | Container images                                                                             | [quay-its.epfl.ch/organization/svc1751](https://quay-its.epfl.ch/organization/svc1751)    | Organisation `svc1751`, team `co2-calculator-devops`; pulls use the read-only robot account                                                                                           |
| Matomo                  | Usage analytics. **Tracking is on in all three environments**, site id 17                    | [enac-webanalytics.epfl.ch/piwik](https://enac-webanalytics.epfl.ch/piwik/)               | Invitation only. Setup: plan [2649](../implementation-plans/2649-matomo-analytics.md)                                                                                                 |
| GitHub                  | Code, CI, and the private GitOps repo `openshift-app-config`                                 | [github.com/EPFL-ENAC](https://github.com/EPFL-ENAC)                                      | EPFL-ENAC organisation membership; the GitOps repo needs an explicit grant                                                                                                            |
| Teams channel           | GlitchTip alert feed                                                                         | Private co2-calculator channel                                                            | Ask the lead developer                                                                                                                                                                |

## EPFL identities behind the service

| Identity                   | Kind                     | Purpose                                                   | Note                                                                                                         |
| -------------------------- | ------------------------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `svc-calcco2-epfl-api`     | Service account (M07583) | Backend access to `api.epfl.ch`                           | **12-month lifetime, expires 2026-10-20.** Renew on [services.epfl.ch](https://services.epfl.ch) before then |
| `co2-calculator-ops`       | Group (S42207)           | Operators of the service; the group to join for OpenShift | Owner: lead developer. Administered by `enacit4research-devops`                                              |
| `co2-calculator-sysadmins` | Group                    | Receives Alertmanager and Icinga mail                     | Membership link in the DRP                                                                                   |
| `enacit4research-devops`   | Group (S36814)           | ENAC-IT devops; owns the Quay organisation contact        | Contains `ENAC-IT-admins`                                                                                    |

Verify which group is actually bound to a namespace rather than trusting
this table:

```bash
oc get rolebindings -n svc1751p-co2-calculator-prod
```

## Onboarding an operator

1. Get added to `co2-calculator-ops` on [groups.epfl.ch](https://groups.epfl.ch)
   by the lead developer, and to `co2-calculator-sysadmins` if you should
   receive alerts.
2. Open the OpenShift console of each cluster once with your EPFL login
   so the account exists, then `oc login --web`.
3. Ask ENAC-IT for the Tempo Grafana, and for Infisical and GlitchTip
   invitations.
4. Ask for read access to `EPFL-ENAC/openshift-app-config`.
5. Read [Operations](04-operations.md) and the DRP, then bookmark the
   links table.

When someone leaves, reverse the list. Group membership drives OpenShift
and alert mail; the rest is per-tool.
