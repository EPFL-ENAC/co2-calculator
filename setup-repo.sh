#!/bin/bash

# Colors for better UX
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to prompt for input with default value
prompt_input() {
    local prompt="$1"
    local default="$2"
    local variable_name="$3"
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " input
        if [ -z "$input" ]; then
            input="$default"
        fi
    else
        read -p "$prompt: " input
        while [ -z "$input" ]; do
            print_warning "This field is required!"
            read -p "$prompt: " input
        done
    fi
    
    eval "$variable_name='$input'"
}

# Function to prompt for yes/no
prompt_yn() {
    local prompt="$1"
    local default="$2"
    local variable_name="$3"
    
    while true; do
        if [ "$default" = "y" ]; then
            read -p "$prompt [Y/n]: " yn
            yn=${yn:-y}
        else
            read -p "$prompt [y/N]: " yn
            yn=${yn:-n}
        fi
        
        case $yn in
            [Yy]* ) eval "$variable_name=true"; break;;
            [Nn]* ) eval "$variable_name=false"; break;;
            * ) print_warning "Please answer yes or no.";;
        esac
    done
}

echo
print_info "🚀 Welcome to the ENAC-IT4R Repository Setup!"
echo
print_info "This script will help you configure your new repository based on the template."

# Auto-detect repository name from git remote
if [ -d ".git" ]; then
    GIT_REMOTE=$(git remote get-url origin 2>/dev/null || echo "")
    if [ -n "$GIT_REMOTE" ]; then
        # Extract repo name from various Git URL formats
        # e.g., git@github.com:EPFL-ENAC/my-repo.git -> my-repo
        # e.g., https://github.com/EPFL-ENAC/my-repo.git -> my-repo
        AUTO_REPO_NAME=$(echo "$GIT_REMOTE" | sed -E 's|.*[:/]([^/]+)\.git$|\1|' | sed -E 's|.*[:/]([^/]+)$|\1|')
        if [ -n "$AUTO_REPO_NAME" ] && [ "$AUTO_REPO_NAME" != "enac-it4r-repo" ]; then
            REPO_NAME="$AUTO_REPO_NAME"
            print_success "Auto-detected repository name: $REPO_NAME"
        fi
        
        # Extract organization/lab name from Git URL
        # e.g., git@github.com:EPFL-ENAC/my-repo.git -> epfl-enac
        # e.g., https://github.com/EPFL-ENAC/my-repo.git -> epfl-enac
        AUTO_LAB_NAME=$(echo "$GIT_REMOTE" | sed -E 's|.*[:/]([^/]+)/[^/]+\.git$|\1|' | sed -E 's|.*[:/]([^/]+)/[^/]+$|\1|' | tr '[:upper:]' '[:lower:]')
        if [ -n "$AUTO_LAB_NAME" ] && [ "$AUTO_LAB_NAME" != "epfl-enac" ]; then
            LAB_NAME="$AUTO_LAB_NAME"
            print_success "Auto-detected lab name: $LAB_NAME"
        elif [ "$AUTO_LAB_NAME" = "epfl-enac" ]; then
            LAB_NAME="epfl-enac"
            print_success "Auto-detected lab name: $LAB_NAME"
        fi
    fi
fi

print_info "Please provide the following information:"
echo

# Collect user inputs
if [ -z "$REPO_NAME" ]; then
    prompt_input "Repository name (e.g., 'my-awesome-project')" "" "REPO_NAME"
else
    prompt_input "Repository name" "$REPO_NAME" "REPO_NAME"
fi
prompt_input "Project description" "" "DESCRIPTION"
if [ -z "$LAB_NAME" ]; then
    prompt_input "Lab name (e.g., 'epfl-cryos')" "" "LAB_NAME"
else
    prompt_input "Lab name" "$LAB_NAME" "LAB_NAME"
fi
prompt_input "Main researchers (comma-separated)" "" "RESEARCHERS"
prompt_input "Lead developer GitHub username (for issue assignments)" "" "LEAD_DEV"

echo
prompt_yn "Does your project support internationalization (i18n)?" "n" "SUPPORTS_I18N"
prompt_yn "Does your project have a data repository?" "y" "HAS_DATA_REPO"
prompt_yn "Do you want to keep the CITATION.cff file for academic citations?" "y" "KEEP_CITATION"
prompt_yn "Do you want to keep the release-please GitHub workflow for automated releases?" "n" "KEEP_RELEASE_PLEASE"

if [ "$HAS_DATA_REPO" = true ]; then
    prompt_input "Data repository location/URL" "" "DATA_REPO_LOCATION"
    prompt_input "Data repository contents (comma-separated list)" "" "DATA_REPO_CONTENTS"
fi

prompt_input "Application data contents (comma-separated list)" "Application-specific data, Configuration files, Smaller datasets" "APP_DATA_CONTENTS"

echo
print_info "🌐 Platform Configuration (optional, press Enter to skip if not applicable):"
prompt_input "Domain for your platform (e.g., 'epfl.ch')" "epfl.ch" "PLATFORM_DOMAIN"
prompt_input "Frontend development port" "9000" "FRONTEND_PORT"
prompt_input "Backend API port" "8060" "BACKEND_PORT"
prompt_input "Traefik dashboard port" "8080" "TRAEFIK_PORT"

echo
prompt_yn "Is this a web platform with frontend/backend?" "y" "IS_WEB_PLATFORM"
if [ "$IS_WEB_PLATFORM" = false ]; then
    prompt_yn "Remove the platform URLs section?" "y" "REMOVE_PLATFORM_URLS"
    prompt_yn "Remove the Tech Stack section?" "y" "REMOVE_TECH_STACK"
    prompt_yn "Remove the Development Environment section?" "y" "REMOVE_DEV_ENV"
fi

echo
print_info "📝 Processing template..."

# Create the new README.md from template
cp README.template.md README.md.new

# Replace placeholders
sed -i '' "s/{ YOUR-REPO-NAME }/$REPO_NAME/g" README.md.new
sed -i '' "s/{ DESCRIPTION }/$DESCRIPTION/g" README.md.new
sed -i '' "s/{ YOUR-LAB-NAME }/$LAB_NAME/g" README.md.new

# Replace platform domain and ports
sed -i '' "s/epfl\.ch/$PLATFORM_DOMAIN/g" README.md.new
sed -i '' "s/localhost:9000/localhost:$FRONTEND_PORT/g" README.md.new
sed -i '' "s/localhost:8060/localhost:$BACKEND_PORT/g" README.md.new
sed -i '' "s/localhost:8080/localhost:$TRAEFIK_PORT/g" README.md.new

# Replace researchers
RESEARCHERS_FORMATTED=$(echo "$RESEARCHERS" | sed 's/,/, /g')
sed -i '' "s/\[Add main researchers\]/$RESEARCHERS_FORMATTED/g" README.md.new

# Handle i18n section
if [ "$SUPPORTS_I18N" = false ]; then
    # Remove the internationalization section
    sed -i '' '/## Internationalization/,/^$/d' README.md.new
fi

# Handle non-web platform sections
if [ "$IS_WEB_PLATFORM" = false ]; then
    if [ "$REMOVE_PLATFORM_URLS" = true ]; then
        # Remove platform URLs section
        sed -i '' '/\*\*Access the platform here:\*\*/,/\*\*$/d' README.md.new
    fi
    
    if [ "$REMOVE_TECH_STACK" = true ]; then
        # Remove Tech Stack section
        sed -i '' '/## Tech Stack/,/^## /c\
## ' README.md.new
    fi
    
    if [ "$REMOVE_DEV_ENV" = true ]; then
        # Remove Development Environment section
        sed -i '' '/### Development Environment/,/^## /c\
## ' README.md.new
    fi
fi

# Handle data repository section
if [ "$HAS_DATA_REPO" = true ]; then
    sed -i '' "s|- Location:|- Location: $DATA_REPO_LOCATION|g" README.md.new
    
    # Format data repo contents
    DATA_REPO_CONTENTS_FORMATTED=$(echo "$DATA_REPO_CONTENTS" | sed 's/,/\n    - /g')
    sed -i '' "s|- Contains:|&\n    - $DATA_REPO_CONTENTS_FORMATTED|g" README.md.new
    # Remove the empty lines after "Contains:"
    sed -i '' '/- Contains:/,/^$/{/^    -$/d}' README.md.new
else
    # Remove the main data repository section
    sed -i '' '/### Main Data Repository/,/^### Application Data/c\
### Application Data' README.md.new
fi

# Handle application data contents
APP_DATA_CONTENTS_FORMATTED=$(echo "$APP_DATA_CONTENTS" | sed 's/,/\n    - /g')
sed -i '' "s/- Application-specific data/- $APP_DATA_CONTENTS_FORMATTED/g" README.md.new
# Remove the default items that were replaced
sed -i '' '/- Configuration files/d' README.md.new
sed -i '' '/- Smaller datasets \.\./d' README.md.new

echo
print_info "🔄 Processing current README.md checklist items..."

# Extract and process checklist items from current README.md
if [ -f "README.md" ]; then
    # Create a temporary file with completed checklist items
    cat > checklist_updates.tmp << EOF

# Setup Checklist Completed

The following items from the original setup checklist have been automatically completed:

- [x] Replace \`{ YOUR-REPO-NAME }\` in all files by the name of your repo
- [x] Replace \`{ YOUR-LAB-NAME }\` in all files by the name of your lab
- [x] Replace \`{ DESCRIPTION }\` with project description
- [x] Replace assignees: githubusernameassignee by the github handle of your assignee
- [x] Handle CITATION.cff file (kept/removed based on preference)
- [x] Handle release-please workflow (kept/removed based on preference)
- [x] Configure project-specific settings

## Remaining Manual Tasks

Please complete these tasks manually:
EOF

# Add conditional note about release-please token
if [ "$KEEP_RELEASE_PLEASE" = true ]; then
    cat >> checklist_updates.tmp << EOF

- [ ] Add token for the github action secrets called: MY_RELEASE_PLEASE_TOKEN (since you kept the release-please workflow)
EOF
fi

cat >> checklist_updates.tmp << EOF
- [ ] Check if you need all the labels: https://github.com/EPFL-ENAC/$REPO_NAME/labels
- [ ] Create your first milestone: https://github.com/EPFL-ENAC/$REPO_NAME/milestones
- [ ] Protect your branch if you're a pro user: https://github.com/EPFL-ENAC/$REPO_NAME/settings/branches
- [ ] [Activate discussion](https://github.com/EPFL-ENAC/$REPO_NAME/settings)

## Helpful links

- [How to format citations ?](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files)
- [Learn how to use github template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
EOF
    
    # Append the checklist to the new README
    cat checklist_updates.tmp >> README.md.new
    rm checklist_updates.tmp
fi

# Replace the original README.md
mv README.md.new README.md

print_success "README.md has been successfully generated!"
echo

# Also update other files with the repo name
print_info "🔄 Updating other files with repository name..."

# Handle CITATION.cff file
if [ "$KEEP_CITATION" = false ]; then
    if [ -f "CITATION.cff" ]; then
        rm "CITATION.cff"
        print_success "Removed CITATION.cff file"
    fi
else
    # Update CITATION.cff with repo name and lab name
    if [ -f "CITATION.cff" ]; then
        sed -i '' "s/{ YOUR-REPO-NAME }/$REPO_NAME/g" "CITATION.cff"
        sed -i '' "s/{ YOUR-LAB-NAME }/$LAB_NAME/g" "CITATION.cff"
        print_success "Updated CITATION.cff"
    fi
fi

# Handle release-please workflow
if [ "$KEEP_RELEASE_PLEASE" = false ]; then
    if [ -f ".github/workflows/release-please.yml" ]; then
        rm ".github/workflows/release-please.yml"
        print_success "Removed release-please.yml workflow"
    fi
else
    # Update release-please workflow with repo name and lab name
    if [ -f ".github/workflows/release-please.yml" ]; then
        sed -i '' "s/{ YOUR-REPO-NAME }/$REPO_NAME/g" ".github/workflows/release-please.yml"
        sed -i '' "s/{ YOUR-LAB-NAME }/$LAB_NAME/g" ".github/workflows/release-please.yml"
        print_success "Updated release-please.yml workflow"
    fi
fi

# Update files that might contain the placeholder
for file in .github/workflows/*.yml .github/ISSUE_TEMPLATE/*.md .github/PULL_REQUEST_TEMPLATE.md; do
    if [ -f "$file" ]; then
        sed -i '' "s/{ YOUR-REPO-NAME }/$REPO_NAME/g" "$file"
        sed -i '' "s/{ YOUR-LAB-NAME }/$LAB_NAME/g" "$file"
        print_success "Updated $file"
    fi
done

# Update assignees if files exist
if [ -n "$LEAD_DEV" ]; then
    for file in .github/ISSUE_TEMPLATE/*.md .github/ISSUE_TEMPLATE/*.yml .github/PULL_REQUEST_TEMPLATE.md; do
        if [ -f "$file" ]; then
            sed -i '' "s/githubusernameassignee/$LEAD_DEV/g" "$file"
            print_success "Updated assignee in $file"
        fi
    done
fi

echo
print_success "🎉 Repository setup completed successfully!"
echo
print_info "📋 Summary of what was configured:"
echo "   • Repository name: $REPO_NAME"
echo "   • Description: $DESCRIPTION"
echo "   • Lab name: $LAB_NAME"
echo "   • Main researchers: $RESEARCHERS_FORMATTED"
echo "   • Lead developer: $LEAD_DEV"
echo "   • Platform domain: $PLATFORM_DOMAIN"
echo "   • Is web platform: $([ "$IS_WEB_PLATFORM" = true ] && echo "Yes" || echo "No")"
echo "   • Internationalization: $([ "$SUPPORTS_I18N" = true ] && echo "Yes" || echo "No")"
echo "   • Data repository: $([ "$HAS_DATA_REPO" = true ] && echo "Yes" || echo "No")"
echo "   • CITATION.cff file: $([ "$KEEP_CITATION" = true ] && echo "Kept and updated" || echo "Removed")"
echo "   • Release-please workflow: $([ "$KEEP_RELEASE_PLEASE" = true ] && echo "Kept and updated" || echo "Removed")"
echo

print_info "🧹 Cleaning up setup files..."

# Remove this script and update Makefile
print_info "Removing setup script and updating Makefile..."

# Create a temporary Makefile without the setup command
sed '/# SETUP SECTION START/,/# SETUP SECTION END/d' Makefile > Makefile.tmp
mv Makefile.tmp Makefile

# Remove the template file since we've generated the final README.md
if [ -f "README.template.md" ]; then
    rm "README.template.md"
    print_success "Removed README.template.md"
fi

print_success "Setup files cleaned up!"
echo

print_warning "📝 Please review the generated README.md and complete any remaining manual tasks listed at the bottom."
print_info "🚀 Your repository is now ready for development!"

# Remove this script
rm -- "$0"
