# Mapping from French HR roles to broad English categories (snake_case)
ROLE_CATEGORY_MAPPING = {
    # Professor roles
    "Professeur titulaire": "professor",
    "Professeur": "professor",
    "Maître d'enseignement et de recherche": "professor",
    # Scientific Collaborator roles
    "Collaborateur scientifique": "scientific_collaborator",
    "Collaborateur scientifique senior": "scientific_collaborator",
    "Informaticien": "scientific_collaborator",
    "Adjoint scientifique": "scientific_collaborator",
    "Assistant scientifique": "scientific_collaborator",
    # Student roles
    "Étudiant-e": "student",
    "Étudiant en échange": "student",
    "Stagiaire étudiant": "student",
    "Student": "student",  # English variant
    # Postdoctoral Researcher
    "Post-Doctorant": "postdoctoral_researcher",
    # Doctoral Assistant
    "Assistant-doctorant": "doctoral_assistant",
    "Doctorant-e en échange": "doctoral_assistant",
    # Trainee roles
    "Apprenti": "trainee",
    "Apprenti Interactive Media Designer": "trainee",
    "Apprenti gardien d'animaux": "trainee",
    "Apprenti informaticien": "trainee",
    "Apprenti laborant en biologie": "trainee",
    "Stagiaire": "trainee",
    "Stagiare": "trainee",  # Typo variant
    # Technical / Administrative Staff
    "Assistant technique": "technical_administrative_staff",
    "Chef de l'animalerie": "technical_administrative_staff",
    "Chef du service technique": "technical_administrative_staff",
    "Chef laborant": "technical_administrative_staff",
    "Collaborateur administratif": "technical_administrative_staff",
    "Assistant-e administratif-ve": "technical_administrative_staff",
    "Secrétaire": "technical_administrative_staff",
    "Chargé-e de communication": "technical_administrative_staff",
    "Ingénieur": "technical_administrative_staff",
    "Collaborateur technique": "technical_administrative_staff",
    "Aide de Laboratoire": "technical_administrative_staff",
    "Ingénieur Système": "technical_administrative_staff",
    "Adjoint": "technical_administrative_staff",
    "Adjoint au Chef du Département": "technical_administrative_staff",
    "Adjoint de section": "technical_administrative_staff",
    "Team Leader": "technical_administrative_staff",
    "Responsable de la laverie": "technical_administrative_staff",
    "Responsable des infrastructures": "technical_administrative_staff",
    "Responsable informatique": "technical_administrative_staff",
    "Responsable magasin principal": "technical_administrative_staff",
    "Adjoint à la direction": "technical_administrative_staff",
    "Animalier": "technical_administrative_staff",
    "Assistant": "technical_administrative_staff",
    "Coordinateur": "technical_administrative_staff",
    "Electronicien": "technical_administrative_staff",
    "Ingénieur Chimiste": "technical_administrative_staff",
    "Journaliste": "technical_administrative_staff",
    "Laborant-e senior": "technical_administrative_staff",
    "Laborantin-e": "technical_administrative_staff",
    "Magasinier": "technical_administrative_staff",
    "Programmeur": "technical_administrative_staff",
    "Spécialiste communication": "technical_administrative_staff",
    "Spécialiste système": "technical_administrative_staff",
    "Spécialiste technique": "technical_administrative_staff",
    "Technicien": "technical_administrative_staff",
    # Other roles
    "Chargé-e de projet": "other",
    "Vétérinaire": "other",
    "Coordinateur-trice de Projets": "other",
    "RSE": "other",
    "Sciencepreneur": "other",
}


def get_function_role(function: str) -> str:
    """
    Get the English category for a French HR role.

    Args:
        french_role: The French HR role name

    Returns:
        The English category name (snake_case), or None if not found
    """
    return ROLE_CATEGORY_MAPPING.get(function, "other")
