# Incident Response

What happens when a security incident is found in this service: who
declares it, how fast it is communicated, and to whom. Covers
vulnerabilities found in the code, exposure of data the service holds,
and compromise of a credential or key.

Service outages that are not security incidents follow the
[Disaster Recovery Plan](security-documentation.md#the-ten-required-documents)
instead. An outage becomes an incident the moment data or credentials
are implicated.

**Reading time**: ~4 minutes

## Who declares an incident

The **DR team lead named in the Disaster Recovery Plan** declares an
incident and owns the response, using the same roster as recovery so
the two never drift apart. Anyone may raise a suspected incident;
declaring it is what starts the clock below.

## Severity and communication timeframes

| Severity     | Trigger                                                                             | Notify the team     | Notify EPFL DSI / ENAC-IT |
| ------------ | ----------------------------------------------------------------------------------- | ------------------- | ------------------------- |
| **Critical** | Data exposure, authentication or authorization bypass, key compromise, service down | Immediately         | **Within 24 hours**       |
| **High**     | Exploitable vulnerability with no evidence of exploitation                          | Same business day   | Within 1 week             |
| **Low**      | Hardening gap with no exploit path                                                  | Next planning cycle | In the periodic review    |

Alerting already delivers the first hop: an alert reaches the sysadmin
group by email roughly 30 seconds after firing, and detection runs
1–10 minutes behind the event itself. See
[Recovery objectives](security-documentation.md#recovery-objectives).

## Personal data

The service stores personal data — headcount entries ingested from
Tableau hold a member name, institutional identifier and FTE. If an
incident exposes them, notify the **EPFL Data Protection Officer
(<dpo@epfl.ch>) within 72 hours** of becoming aware, in addition to the
timeframes above.

> **⚠️ Do not state that this service processes no personal data.** It
> does. Any questionnaire answer claiming otherwise is wrong and
> discredits the rest of the submission.

## Confidentiality

Incident communications are **restricted while the incident is open**:
the DR team and EPFL DSI only, and the tracking issue stays private
until a fix ships. After the fix is deployed the details may be shared
or published.

This is coordinated disclosure, not secrecy — the constraint is
"not before the fix", not "never".

## Procedure

1. **Report** the suspected incident to the development team
   immediately.
2. **Declare and classify.** The DR team lead assigns a severity from
   the table above, which sets every deadline that follows.
3. **Contain.** Revoke or rotate an exposed credential first — rotation
   blast radius is documented in
   [Encryption and Key Management](encryption.md#inventory).
4. **Fix.** Critical findings block all other work and ship as soon as
   a fix is verified; lower severities follow the normal release path.
5. **Notify** EPFL DSI within the timeframe for the severity, and the
   Data Protection Officer within 72 hours if personal data is
   involved.
6. **Record.** Log the incident, its resolution and its lessons in a
   private tracking issue, and update whichever documents the incident
   proved wrong.

## After the incident

Every incident ships a regression test that would have caught it, the
same rule as any bug fix. If the incident revealed a documentation gap,
the fixing PR updates the document — a lesson recorded only in an issue
is a lesson lost.
