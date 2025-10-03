# enac-it4r-repo

Template with licences / github templates and contributing processes

## For New Repositories

If you're setting up a new repository based on this template:

1. **First-time setup:**

   ```bash
   make setup
   ```

   This will run an interactive script to configure your repository with project-specific details.

2. **Regular development setup:**
   ```bash
   make install
   ```
   This installs dependencies and sets up git hooks.

## For Template Development

To set up the development environment and git hooks for working on this template itself, run:

```bash
make install
```

This will install npm dependencies and configure git hooks using Lefthook.

## Available Commands

- `make setup` - **For new repositories**: Interactive setup from template
- `make install` - Install dependencies and set up git hooks
- `make clean` - Clean node_modules and package-lock.json
- `make uninstall` - Remove git hooks and clean dependencies
- `make help` - Show available commands

# Todo when setting up your github repo

- [ ] Replace `{ YOUR-REPO-NAME }` in all files by the name of your repo
- [ ] Replace `{ YOUR-LAB-NAME }` in all files by the name of your lab (.e.G epfl-cryos cf .github/workflows/deploy.yml)
- [ ] Replace assignees: githubusernameassignee by the github handle of your lead dev
- [ ] Modifiy or remove the `CITATION.cff` file.
- [ ] ADD/REMOVE .github/workflows/release-please.yml depending on your proejct.
  - [ ] Add token for the github action secrets called: MY_RELEASE_PLEASE_TOKEN

# Optional TODOs

- If you created a repo outstide the organization EPFL-ENAC, please replace every instances
- Modify .github/.copilot-instructions.md if need be
- Check if you need all the labels: https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/labels
- Create your first milestone: https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/milestones
- Protect your branch if you're a pro user: https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/settings/branches
- [Activate discussion](https://github.com/EPFL-ENAC/{ YOUR-REPO-NAME }/settings)

# Helpful links

- [How to format citations ?](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)
- [Learn how to use github template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
