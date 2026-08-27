# Other Documentation

This site is the **developer documentation**. Three other documentation
sets exist, each with its own repository and audience. Look here first
when a question is not about the code.

| Set                    | Audience                                       | Where                                                                                                             |
| ---------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| **User documentation** | People entering data and reading results       | [epfl-enac.github.io/co2-calculator-user-doc](https://epfl-enac.github.io/co2-calculator-user-doc/)               |
| **Backoffice guide**   | Administrators: roles, factors, data contracts | [epfl-enac.github.io/co2-calculator-back-office-doc](https://epfl-enac.github.io/co2-calculator-back-office-doc/) |
| **Storybook**          | Components, design tokens, UI states           | [co2-calculator-storybook.epfl.ch](https://co2-calculator-storybook.epfl.ch/)                                     |
| **Developer docs**     | Architecture, backend, frontend, plans         | This site                                                                                                         |

Edit them where they live:

- User documentation — [`EPFL-ENAC/co2-calculator-user-doc`](https://github.com/EPFL-ENAC/co2-calculator-user-doc/tree/main/docs)
- Backoffice guide — [`EPFL-ENAC/co2-calculator-back-office-doc`](https://github.com/EPFL-ENAC/co2-calculator-back-office-doc/tree/main/docs)
- Storybook stories — `frontend/storybook/stories/` and `frontend/src/components/**/*.stories.ts`

## Frequently wanted pages

- **CSV column contracts** —
  [Data description](https://epfl-enac.github.io/co2-calculator-back-office-doc/data-description)
  in the backoffice guide. The backend's emission-type resolution depends
  on these; see [Emission type resolution](../backend/emission-type-resolution.md).
- **What a role may do** —
  [Roles](https://epfl-enac.github.io/co2-calculator-back-office-doc/roles/)
  in the backoffice guide. The enforcement side is
  [Permission System](../backend/06-PERMISSION-SYSTEM.md).
- **Design tokens** —
  [the live token reference](https://co2-calculator-storybook.epfl.ch/?path=/story/documentation-design-tokens--documentation)
  renders the real values; [Design Tokens](../frontend/02-design-tokens.md)
  explains the architecture behind them.

Do not copy content from those sites into this one. A second copy is how
documentation drifts into stating something false.
