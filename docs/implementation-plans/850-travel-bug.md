# Travel Bugs implementation plan

## Traveler field bug

In the travel module, the traveler field, which is a dropdown for Unit Managers and a read-only field for standard users, is fragile, tends to break, and seems to behave differently depending on the environment. Here is the reported bug:

- As a Unit Manager in stage, I get the message "No headcount members found. Add members in the Headcount module first." although I have headcount members in the system.

The expected behavior is the following:

- As a Unit Manager:
  - If Headcount is not validated, or if there are no entries in the Headcount module, I should get the message "No headcount members found. Add members in the Headcount module first."
  - If headcount is available and validated, I should see a dropdown with the list of entries in the Headcount module, and I should be able to select one of them.
- As a Standard User:
  - If Headcount is not validated, or if there are no entries in the Headcount module, I should get the message "You have not been validated in the headcount. Please contact your unit manager."
  - If headcount is available and validated, I should see the name of the entry in the Headcount module that is assigned to me. The assignment is done via the institutional_id in a read-only field.

This should be fixed and tested in all environments to make sure the behavior is consistent. Unit tests should be added to cover the different scenarios.

## Travel Table visibility

The travel table's expected behavior is not what is expected. Here is the reported bug:

As a Unit Manager, I only see the entries in the traveler table assigned to me (with the same institutional_id).

The expected behavior is the following:

- A Unit Manager must see all entries in the travel table regardless of the institutional_id.
- A Standard User should only see the entry in the travel table that is assigned to them via the institutional_id, regardless of whether the form was filled in by them or by their Unit Manager.

This should be fixed and tested in all environments to make sure the behavior is consistent. Unit tests should be added to cover the different scenarios.
