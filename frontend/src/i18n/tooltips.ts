export default {
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // HOW TO EDIT THIS FILE
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  //
  // Each entry below has an English (en) and a French (fr) translation.
  // To update the text of a tooltip, simply edit the words between the quotes:
  //
  //   en: 'Write your English text here.',
  //   fr: 'Écrivez votre texte en français ici.',
  //
  // To HIDE a tooltip icon completely (so it does not appear at all),
  // set both en and fr to empty strings:
  //
  //   en: '',
  //   fr: '',
  //
  // ⚠️  IMPORTANT: Never delete an entry line. If a key is missing, the app
  //     will display the raw key name as visible text (e.g. "module-buildings-title")
  //     instead of showing nothing.
  //
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  // ─── ACCESSIBILITY LABEL ──────────────────────────────────────────────────
  // This short text is read aloud by screen-readers (for users who rely on
  // them) when they focus any tooltip icon. It is never visible on screen.
  // You probably do not need to change this.

  'module-info-label': {
    en: 'More information',
    fr: "Plus d'informations",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // MODULE PAGE TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Each module page has a small (ℹ) icon in the top-right corner of the page.
  // The text you write here appears when a user clicks that icon.
  // Leave en/fr empty ("") to hide the icon for that module entirely.
  //
  // Module order in the app:
  //   Headcount → Process Emissions → Buildings → Equipment →
  //   External Cloud & AI → Professional Travel → Purchases → Research Facilities

  'module-headcount-title': {
    en: 'The carbon footprint linked to this module covers Scope 3 (indirect emissions).',
    fr: 'L’empreinte carbone liée à ce module relève du Scope 3 (émissions indirectes).',
  },
  'module-process-emissions-title': {
    en: 'The carbon footprint calculated in this module covers Scope 1 (direct emissions).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 1 (émissions directes).',
  },
  'module-buildings-title': {
    en: 'The carbon footprint calculated in this module covers Scope 1 (on-site energy combustion) and Scope 2 (purchased electricity for heating, cooling, ventilation, and lighting).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 1 (combustion d’énergie sur site) et du Scope 2 (électricité achetée pour le chauffage, le refroidissement, la ventilation et l’éclairage).',
  },
  'module-equipment-title': {
    en: 'The carbon footprint calculated in this module covers Scope 2 (electricity consumption).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 2 (consommation d’électricité).',
  },
  'module-external-cloud-and-ai-title': {
    en: 'The carbon footprint calculated in this module covers Scope 3 (indirect emissions).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 3 (émissions indirectes).',
  },
  'module-professional-travel-title': {
    en: 'The carbon footprint calculated in this module covers Scope 3 (indirect emissions).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 3 (émissions indirectes).',
  },
  'module-purchase-title': {
    en: 'The carbon footprint calculated in this module covers Scope 3 (indirect emissions).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 3 (émissions indirectes).',
  },
  'module-research-facilities-title': {
    en: 'The carbon footprint calculated in this module covers Scope 3 (indirect emissions).',
    fr: 'L’empreinte carbone calculée dans ce module relève du Scope 3 (émissions indirectes).',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // SUBMODULE SECTION TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Each module page is divided into collapsible sub-sections
  // (e.g. "Scientific Equipment" inside the Equipment module).
  // These tooltips appear as a (ℹ) icon next to the sub-section title.
  // Leave en/fr empty ("") to hide the icon for that sub-section.

  // ── Headcount ──────────────────────────────────────────────────────────────
  'module-headcount-submodule-member': {
    en: "Member's name, their function, SCIPER, and FTE are automatically displayed based on HR data for the reference calendar year. To ensure consistency with its records, this data cannot be edited or deleted. To include additional members not captured by the automatic upload, use the Add FTE option.",
    fr: "Le nom du membre, sa fonction, SCIPER et son EPT sont automatiquement affichés à partir des données RH de l'année civile de référence. Afin de garantir la cohérence avec les données RH, ces informations ne peuvent être ni modifiées ni supprimées. Pour ajouter des membres supplémentaires non pris en compte par l'importation automatique, utilisez l'option « Ajouter un EPT",
  },
  'module-headcount-submodule-student': {
    en: 'Due to data-protection rules, students names and individual FTE are not shown automatically.',
    fr: 'En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement',
  },

  // ── Process Emissions ──────────────────────────────────────────────────────
  'module-process-emissions-submodule-process_emissions': { en: '', fr: '' },

  // ── Buildings ──────────────────────────────────────────────────────────────
  'module-buildings-submodule-building': {
    en: 'Room surfaces and types are extracted from the centralized Archibus database, and energy consumption data is provided based on measurements specific to EPFL buildings. An allocation ratio has been added to indicate whether the space is shared or not; in the case of shared use, the ratio is less than 1.',
    fr: ' Les surfaces et types de locaux sont extraites de la base de données centralisée Archibus et les données de consommation énergétique par type de surface sont fournies sur la base de mesures spécifiques aux bâtiments EPFL. Le ratio alloué a été ajouté pour spécifier si ce local est mutualisé ou pas. Dans le cas d’une mutualisation, le ratio est inférieur à 1.',
  },
  'module-buildings-submodule-energy_combustion': { en: '', fr: '' },

  // ── Equipment ──────────────────────────────────────────────────────────────
  'module-equipment-submodule-scientific': {
    en: 'Check that the data for your scientific equipment are accurate, especially by updating the active and standby use of each piece of equipment.',
    fr: "Vérifiez que les données de vos équipements scientifiques sont correctes, en particulier en mettant à jour l'utilisation active et standby de chaque équipement.",
  },
  'module-equipment-submodule-it': {
    en: 'Check that the data for your IT equipment are accurate, especially by updating the active and standby use of each piece of equipment.',
    fr: "Vérifiez que les données de vos équipements scientifiques sont correctes, en particulier en mettant à jour l'utilisation active et standby de chaque équipement.",
  },
  'module-equipment-submodule-other': {
    en: 'Check that the data for your other equipment are accurate, especially by updating the active and standby use of each piece of equipment.',
    fr: "Vérifiez que les données de vos autres équipements  sont correctes, en particulier en mettant à jour l'utilisation active et standby de chaque équipement.",
  },

  // ── External Cloud & AI ────────────────────────────────────────────────────
  'module-external-cloud-and-ai-submodule-external_clouds': {
    en: 'Enter the provider name, service type, amount spent, and currency.',
    fr: 'Saisissez le nom du fournisseur, le type de service, le montant dépensé et la devise.',
  },
  'module-external-cloud-and-ai-submodule-external_ai': {
    en: 'Enter the provider name, usage type, number of users, and usage frequency.',
    fr: `Saisissez le nom du fournisseur, le type d'usage, le nombre d'utilisateurs·trice et la fréquence d'utilisation.`,
  },

  // ── Professional Travel ────────────────────────────────────────────────────
  'module-professional-travel-submodule-plane': {
    en: 'The flights listed in the table are provided by the EPFL Central Travel Agency. If any flights are missing, you can add them manually.',
    fr: "Les vols affichés dans le tableau proviennent de l'agence de voyage central EPFL. S'il manque des vols, il est possible de les saisir manuellement.",
  },
  'module-professional-travel-submodule-train': {
    en: 'Enter your train trips manually, whether they were taken in Switzerland or abroad. ',
    fr: "Saisissez manuellement les voyages effectués en train qu'ils soient en Suisse ou à l'étranger.",
  },

  // ── Purchases ──────────────────────────────────────────────────────────────
  'module-purchase-submodule-scientific_equipment': {
    en: 'This table lists purchases that are automatically categorized as scientific equipment based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme équipements scientifiques selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).',
  },
  'module-purchase-submodule-it_equipment': {
    en: 'This table lists purchases that are automatically categorized as IT equipment based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse). For this category, EPFL-specific emission factors are used.',
    fr: "Ce tableau regroupe les achats automatiquement catégorisés comme équipements informatiques selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse). Pour cette catégorie, les facteurs d'émission spécifiques à l'EPFL sont utilisés.",
  },
  'module-purchase-submodule-consumable_accessories': {
    en: 'This table lists purchases that are automatically categorized as consumables and accessories based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme consommables et accessoires selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).',
  },
  'module-purchase-submodule-biological_chemical_gaseous_product': {
    en: 'This table lists purchases that are automatically categorized as biological, chemical et gaseous products based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme produits biologiques chimiques et gazeux  selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).',
  },
  'module-purchase-submodule-services': {
    en: 'This table lists purchases that are automatically categorized as services based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme services selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).',
  },
  'module-purchase-submodule-vehicles': {
    en: 'This table lists purchases that are automatically categorized as vehicles based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme véhicules selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).',
  },
  'module-purchase-submodule-other_purchases': {
    en: 'This table lists all remaining purchases whose classification codes do not correspond to any of the specific main categories.',
    fr: 'Ce tableau regroupe tous les achats restants dont les codes de classification ne correspondent à aucune des catégories principales spécifiques.',
  },
  'module-purchase-submodule-purchases_centralized': {
    en: 'Enter annual consumption values if your unit uses any of the items listed below.',
    fr: 'Saisissez les consommations annuelles si votre unité utilise les éléments listés ci-dessous.',
  },

  // ── Research Facilities ────────────────────────────────────────────────────
  'module-research-facilities-submodule-research-facilities': {
    en: 'If one or more research facilities are missing in the table, please contact us for further details.',
    fr: "Si une ou plusieurs infrastructures de recherche manquent dans la table, n'hésitez pas à nous contacter afin que nous puissions vous fournir plus de détails.",
  },
  'module-research-facilities-submodule-animal_facilities': {
    en: 'The carbon footprint from the rodent and fish facilities are allocated to individual units based on their use of housing units (e.g., cages and aquariums) throughout the year. These footpritns are calculated based on the Process emissions, Buildings, Equipment, and Purchases, with the annual number of housing units serving as the allocation key.',
    fr: "L'empreinte carbone des animaleries (rongeurs et poissons) est attribuée aux unités au prorata du nombre d'hébergements (cages, aquariums) occupés par an.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // DATA-ENTRY FORM TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // When a user opens the form to add or edit a row, a (ℹ) icon can appear
  // at the top of that form. The text below is what they see when they click it.
  // Leave en/fr empty ("") to hide the icon for that form.

  // ── Headcount ──────────────────────────────────────────────────────────────
  'module-headcount-submodule-member-form': {
    en: 'Use this option to manually add members not captured by the automatic upload. All fields must be filled to add a memeber. Unlike the auto-uploaded data, manually added members can be edited or deleted at any time',
    fr: 'Utlisez cette option pout ajouter manuellement des membres manquants. Tous les champs doivent être renseignés pour ajouter un memebre. Contrairement aux membres affichés automatiquements, les membres ajoutés manuellements peuvent être modifiés ou supprimés à tout moment.',
  },
  'module-headcount-submodule-student-form': {
    en: 'Enter the total number of FTE of students who worked in your unit over the year',
    fr: "Saisissez le total des EPT des étudiant·es ayant travaillé dans votre unité sur l'année",
  },

  // ── Process Emissions ──────────────────────────────────────────────────────
  'module-process-emissions-submodule-process_emissions-form': {
    en: 'Please select one or more process and fugitive emission sources from the list, if applicable. The quantity of each greenhouse gas must be estimated prior to entry (taking into account, for example, that only a fraction of X % of the SF₆ used is actually emitted).',
    fr: "Veuillez sélectionner dans la liste la ou les sources d'émissions de procédés et fugitives, le cas échéant. La quantité de chaque gaz à effet de serre doit être estimée avant sa saisie (en tenant compte, par exemple, du fait que seule une fraction X % du SF₆ utilisé est réellement émise).",
  },

  // ── Buildings ──────────────────────────────────────────────────────────────
  'module-buildings-submodule-building-form': {
    en: "Please add any missing premises to the list above. If the information provided is incorrect, please contact your faculty's infrastructure manager to update the centralized database.",
    fr: "Veuillez ajouter tout local manquant à la liste ci-dessus. Si les informations fournies ne sont pas correctes, veuillez contacter le ou la responsable des infrastructures de votre faculté afin de faire mettre à jour les données figurant dans la base de données centralisée de l'EPFL (Archibus).",
  },
  'module-buildings-submodule-energy_combustion-form': {
    en: 'Please select one or more combustion sources (fossil or non-fossil) from the list if they are not included in the main module.',
    fr: 'Veuillez sélectionner dans la liste la ou les sources de combustion (fossiles ou non fossiles) si celles-ci ne sont pas prises en compte dans le module principal.',
  },

  // ── Equipment ──────────────────────────────────────────────────────────────
  'module-equipment-submodule-scientific-form': {
    en: 'Please add any missing scientific equipment to the list above. Note that you will need to carry this change over to your next inventory update, as it is not automatically reflected through the CO₂ Calculator.',
    fr: "Veuillez ajouter les équipements scientifiques qui manquent dans la liste ci-dessus. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour de l'inventaire, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.",
  },
  'module-equipment-submodule-it-form': {
    en: 'Please add any missing IT equipment to the list above. Note that you will need to carry this change over to your next inventory update, as it is not automatically reflected through the CO₂ Calculator.',
    fr: "Veuillez ajouter les équipements informatiques qui manquent dans la liste ci-dessus. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour de l'inventaire, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.",
  },
  'module-equipment-submodule-other-form': {
    en: 'Please add any missing other equipment to the list above. Note that you will need to carry this change over to your next inventory update, as it is not automatically reflected through the CO₂ Calculator.',
    fr: "Veuillez ajouter les autres équipements qui manquent dans la liste ci-dessus. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour de l'inventaire, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.",
  },

  // ── External Cloud & AI ────────────────────────────────────────────────────
  'module-external-cloud-and-ai-submodule-external_clouds-form': {
    en: 'Please select the supplier(s) from the list, then provide the service type, total spent, and currency. To save time, you can pre-fill and import a CSV file.',
    fr: 'Veuillez sélectionner le ou les fournisseurs dans la liste, puis préciser le type de service, le montant dépensé et la devise associée. Pour faciliter la saisie, vous pouvez préalablement remplir et importer un fichier CSV.',
  },
  'module-external-cloud-and-ai-submodule-external_ai-form': { en: '', fr: '' },

  // ── Professional Travel ────────────────────────────────────────────────────
  'module-professional-travel-submodule-plane-form': {
    en: 'Each leg of the trip must be entered as a separate trip. For example, for a flight departing from Geneva and arriving in Los Angeles with a layover in Amsterdam: Geneva-Amsterdam, Amsterdam-Los Angeles.',
    fr: 'Chaque étape du trajet doit être saisie comme un déplacement distinct. Par exemple, pour un vol au départ de Genève à destination de Los Angeles avec une escale à Amsterdam : Genève-Amsterdam, Amsterdam-Los-Angeles.',
  },
  'module-professional-travel-submodule-train-form': {
    en: 'Each leg of the trip must be entered as a separate trip. For example, for a train trip from Lausanne to Mannheim: Lausanne–Bern, Bern–Basel, Basel–Mannheim.',
    fr: 'Chaque étape du trajet doit être saisie comme un déplacement distinct. Par exemple, pour un trajet en train  au départ de Lausanne à destination de Mannheim  : Lausanne-Berne, Berne-Bale, Bale-Mannheim.',
  },

  // ── Purchases ──────────────────────────────────────────────────────────────
  'module-purchase-submodule-scientific_equipment-form': {
    en: 'Please add any missing scientific equipment purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory.',
    fr: "Veuillez ajouter les achats d'équipements scientifiques manquants dans la liste ci-dessus. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires.",
  },
  'module-purchase-submodule-it_equipment-form': {
    en: 'Please add any missing IT equipment purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory.',
    fr: "Veuillez ajouter les achats d'équipements IT manquants dans la liste ci-dessus. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires.",
  },
  'module-purchase-submodule-consumable_accessories-form': {
    en: 'Please add any missing consumables & accessories purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory.',
    fr: "Veuillez ajouter les achats de consommables et accessoires manquants dans la liste ci-dessus. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires.",
  },
  'module-purchase-submodule-biological_chemical_gaseous_product-form': {
    en: 'Please add any missing biological, chemical & gaseous products purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory.',
    fr: "Veuillez ajouter les achats de produits biologiques chimiques et gazeux manquants dans la liste ci-dessus. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires.",
  },
  'module-purchase-submodule-services-form': {
    en: 'Please add any missing services purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory.',
    fr: "Veuillez ajouter les achats de services manquants dans la liste ci-dessus. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires.",
  },
  'module-purchase-submodule-vehicles-form': {
    en: "Please add any missing vehicle-related purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory. Enter any vehicle-related purchases paid with unit's credit card here (e.g. fuel, car rentals, tolls, parking, or vehicle maintenance).",
    fr: "Veuillez ajouter les achats liés aux véhicules manquants dans la liste ci-dessus. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires. Veuillez ajouter tous les achats liés aux véhicules réglés avec la carte de crédit de l'unité (ex. le carburant, les locations de voiture, les péages, les frais de stationnement ou l'entretien des véhicules.",
  },
  'module-purchase-submodule-other_purchases-form': {
    en: 'Please add any missing other purchases to the list above. The item description, UNSPSC category (typology), and total amount spent are mandatory.',
    fr: "Veuillez ajouter les achats d'autre articles manquants. La description de l'article, la catégorie UNSPSC (typologie) et le montant total dépensé sont obligatoires.",
  },
  'module-purchase-submodule-purchases_centralized-form': {
    en: 'For the liquid nitrogen, if you know your consumption in litres, convert using the following factor - 1 litre = 0.81kg (density of liquid nitrogen at boiling point).',
    fr: "Pour l'azote liquide, si vous connaissez votre consommation en litres, convertissez à l'aide du acteur suivant - 1 litre = 0,81 kg (densité de l'azote liquide à son point d'ébullition).",
  },

  // ── Research Facilities ────────────────────────────────────────────────────
  'module-research-facilities-submodule-research-facilities-form': {
    en: '',
    fr: '',
  },
  'module-research-facilities-submodule-animal_facilities-form': {
    en: '',
    fr: '',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // TABLE COLUMN TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Each data table has column headers. A (ℹ) icon can appear next to a column
  // name to explain what that column means or how to fill it in.
  // Leave en/fr empty ("") to hide the icon for that column.
  //
  // Note: to wire up a (ℹ) icon on a new column, you also need to add
  //   tooltip: 'your-key'
  // to that column's definition in frontend/src/constant/module-config/<module>.ts.

  // ── Headcount — FTE members table ──────────────────────────────────────────
  'module-headcount-submodule-member-table-name': { en: '', fr: '' },
  'module-headcount-submodule-member-table-sius_code': { en: '', fr: '' },
  'module-headcount-submodule-member-table-user_institutional_id': {
    en: '',
    fr: '',
  },
  'module-headcount-submodule-member-table-fte': { en: '', fr: '' },

  // ── Headcount — students table ──────────────────────────────────────────────
  'module-headcount-submodule-student-table-fte': { en: '', fr: '' },

  // ── Process Emissions — table ───────────────────────────────────────────────
  'module-process-emissions-submodule-process_emissions-table-category': {
    en: '',
    fr: '',
  },
  'module-process-emissions-submodule-process_emissions-table-subcategory': {
    en: '',
    fr: '',
  },
  'module-process-emissions-submodule-process_emissions-table-quantity': {
    en: '',
    fr: '',
  },
  'module-process-emissions-submodule-process_emissions-table-kg_co2eq': {
    en: '',
    fr: '',
  },

  // ── Buildings — rooms table ─────────────────────────────────────────────────
  'module-buildings-submodule-building-table-building_name': { en: '', fr: '' },
  'module-buildings-submodule-building-table-room_name': { en: '', fr: '' },
  'module-buildings-submodule-building-table-room_type': { en: '', fr: '' },
  'module-buildings-submodule-building-table-room_surface_square_meter': {
    en: '',
    fr: '',
  },
  'module-buildings-submodule-building-table-room_allocation_ratio': {
    en: 'Ratio of the room surface allocated to the unit. Default is 1 (100%).',
    fr: "Ratio de surface du local alloué à l'unité. Par défaut, 1 (100%).",
  },
  'module-buildings-submodule-building-table-heating_kwh_per_square_meter': {
    en: 'Annual heating energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie de chauffage calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },
  'module-buildings-submodule-building-table-cooling_kwh_per_square_meter': {
    en: 'Annual cooling energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie de refroidissement calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },
  'module-buildings-submodule-building-table-ventilation_kwh_per_square_meter':
    {
      en: 'Annual ventilation energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
      fr: "Consommation annuelle d'énergie de ventilation calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
    },
  'module-buildings-submodule-building-table-lighting_kwh_per_square_meter': {
    en: 'Annual lighting energy consumption calculated from room surface and SIA room type benchmark (kWh/m²)',
    fr: "Consommation annuelle d'énergie d'éclairage calculée à partir de la surface du local et du benchmark SIA par type de local (kWh/m²)",
  },
  'module-buildings-submodule-building-table-kg_co2eq': { en: '', fr: '' },

  // ── Buildings — energy combustion table ────────────────────────────────────
  'module-buildings-submodule-energy_combustion-table-name': { en: '', fr: '' },
  'module-buildings-submodule-energy_combustion-table-unit': { en: '', fr: '' },
  'module-buildings-submodule-energy_combustion-table-quantity': {
    en: '',
    fr: '',
  },
  'module-buildings-submodule-energy_combustion-table-kg_co2eq': {
    en: '',
    fr: '',
  },

  // ── Equipment — scientific table ────────────────────────────────────────────
  'module-equipment-submodule-scientific-table-name': {
    en: '',
    fr: '',
  },
  'module-equipment-submodule-scientific-table-equipment_class': {
    en: 'The equipment class determines the average power values used to calculate carbon footprints. Update the class in your inventory if it is incorrect.',
    fr: "La classe de l'équipement détermine les valeurs de puissance moyenne utilisées pour le calcul des empreintes carbone. Mettez à jour la classe  dans votre inventaire si celle-ci n'est pas appropriée.",
  },
  'module-equipment-submodule-scientific-table-sub_class': {
    en: 'The sub-class allows a more precise determination of the average power values for some equipment classes.',
    fr: "La sous-classe permet une détermination plus précise des valeurs de puissance moyenne pour certaines classes d'équipements.",
  },
  'module-equipment-submodule-scientific-table-active_usage_hours_per_week': {
    en: 'Number of hours per week the equipment is actively in use. Some generic time values have been pre-filled. Please update to make them more specific to your equipment use. Active and standby hours combined cannot exceed 168 h/wk.',
    fr: 'Nombre d’heures par semaine pendant lesquelles l’équipement est activement utilisé. Certaines valeurs génériques ont été préremplies. Veuillez les mettre à jour afin qu’elles correspondent plus précisément à l’utilisation de votre équipement. Le total des heures actives et des heures en veille ne peut pas dépasser 168 h/semaine.',
  },
  'module-equipment-submodule-scientific-table-standby_usage_hours_per_week': {
    en: 'Number of hours per week the equipment is in standby use. Some generic time values have been pre-filled. Please update to make them more specific to your equipment use. Active and standby hours combined cannot exceed 168 h/wk.',
    fr: 'Nombre d’heures par semaine pendant lesquelles l’équipement est utilisé en mode standby. Certaines valeurs génériques ont été préremplies. Veuillez les mettre à jour afin qu’elles correspondent plus précisément à l’utilisation de votre équipement. Le total des heures actives et des heures en veille ne peut pas dépasser 168 h/semaine.',
  },
  'module-equipment-submodule-scientific-table-active_power_w': {
    en: 'The average active power is indicated by class. It may not fully represent the power of your equipment, in which case you can request a change via the Comment button  on that row. Please note that we do not want the maximum power value, which can be very different from the average power.',
    fr: "La puissance active moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas vous pouvez demander une modification via le bouton Commentaire  de la ligne concernée. Attention, nous ne voulons pas avoir la valeur de puissance maximale qui peut être très différente de la puissance moyenne.",
  },
  'module-equipment-submodule-scientific-table-standby_power_w': {
    en: 'The average standby power is indicated by class. It may not fully represent the power of your equipment, in which case you can request a change via the Comment button on that row.',
    fr: "La puissance standby moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas vous pouvez demander une modification via le bouton Commentaire de la ligne concernée.",
  },
  'module-equipment-submodule-scientific-table-kg_co2eq': {
    en: 'The uncertainty of these values may be high and depends on the representativeness of the power, the hours of use, and the use parameters.',
    fr: "L'incertitude de ces valeurs peut être haute et dépend de la représentativité de la puissance, des heures d'utilisation et des paramètre d'utilisation.",
  },
  'module-equipment-submodule-scientific-table-t_co2eq': {
    en: 'The uncertainty of these values may be high and depends on the representativeness of the power, the hours of use, and the use parameters.',
    fr: "L'incertitude de ces valeurs peut être haute et dépend de la représentativité de la puissance, des heures d'utilisation et des paramètres d'utilisation.",
  },

  // ── Equipment — IT and other tables ────────────────────────────────────────
  'module-equipment-submodule-it-table-name': {
    en: '',
    fr: '',
  },
  'module-equipment-submodule-other-table-name': {
    en: '',
    fr: '',
  },

  // ── External Cloud & AI — cloud services table ──────────────────────────────
  'module-external-cloud-and-ai-submodule-external_clouds-table-provider': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_clouds-table-service_type': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_clouds-table-spent_amount': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_clouds-table-currency': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_clouds-table-kg_co2eq': {
    en: '',
    fr: '',
  },

  // ── External Cloud & AI — AI services table ─────────────────────────────────
  'module-external-cloud-and-ai-submodule-external_ai-table-provider': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_ai-table-usage_type': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_ai-table-fte_count': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_ai-table-requests_per_user_per_day':
    { en: '', fr: '' },
  'module-external-cloud-and-ai-submodule-external_ai-table-kg_co2eq': {
    en: '',
    fr: '',
  },

  // ── Research Facilities — research facilities table ─────────────────────────
  'module-research-facilities-submodule-research-facilities-table-researchfacility_name':
    { en: '', fr: '' },
  'module-research-facilities-submodule-research-facilities-table-use': {
    en: '',
    fr: '',
  },
  'module-research-facilities-submodule-research-facilities-table-use_unit': {
    en: '',
    fr: '',
  },
  'module-research-facilities-submodule-research-facilities-table-kg_co2eq': {
    en: '',
    fr: '',
  },

  // ── Research Facilities — animal facilities table ───────────────────────────
  'module-research-facilities-submodule-animal_facilities-table-researchfacility_name':
    {
      en: '',
      fr: '',
    },
  'module-research-facilities-submodule-animal_facilities-table-researchfacility_type':
    {
      en: '',
      fr: '',
    },
  'module-research-facilities-submodule-animal_facilities-table-use': {
    en: "For EPFL's rodent and fish animal facilities, only the animal housing component is considered. The Phenotyping Unit (UDP) and the Transgenesis Platform (TCF) are not included.",
    fr: "Pour l'utilisation des animaleries rongeurs et poissons à l'EPFL, nous ne considérons que la partie hébergement des animaux et pas ce qui concerne l'unité de phénotypage (UDP) et la plateforme de transgénèse (TCF).",
  },
  'module-research-facilities-submodule-animal_facilities-table-kg_co2eq': {
    en: '',
    fr: '',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // MODULE CHART TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Each module results section contains a breakdown chart. A (ℹ) icon can
  // appear next to the chart title to give users context about what is
  // included in — or excluded from — the visualisation.
  // Leave en/fr empty ("") to hide the icon for that module's chart.
  //
  // Module order in the app:
  //   Headcount → Process Emissions → Buildings → Equipment →
  //   External Cloud & AI → Professional Travel → Purchases → Research Facilities

  'module-headcount-charts': {
    en: '',
    fr: '',
  },
  'module-process-emissions-charts': {
    en: '',
    fr: '',
  },
  'module-buildings-charts': {
    en: '',
    fr: '',
  },
  'module-equipment-charts': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-charts': {
    en: '',
    fr: '',
  },
  'module-professional-travel-charts': {
    en: '',
    fr: '',
  },
  'module-purchase-charts': {
    en: '',
    fr: '',
  },
  'module-research-facilities-charts': {
    en: '',
    fr: '',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RESULTS PAGE — SUMMARY STAT CARDS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // The results overview page shows summary cards (e.g. total footprint,
  // Paris Agreement target). Each card can have a (ℹ) icon with extra context.

  'results-stats-total-unit-carbon-footprint-title': {
    en: 'A km driven by car is equivalent to 0.3 kg CO₂-eq',
    fr: 'Un km parcouru en voiture est équivalent à 0.3 kg CO₂-eq',
  },
  'results-stats-paris-agreement-title': {
    en: 'Following the Paris Agreement.',
    fr: "Conformément à l'accord de Paris.",
  },
  'results-stats-waste-title': {
    en: 'All waste is recycled, apart from domestic waste which is incinerated.',
    fr: "Tous les déchets sont recyclés à l'exception de déchets municipaux qui sont incinérés.",
  },
  'results-stats-embodied-energy-title': {
    en: 'This corresponds to embedded energy carbon footprints in buildings.',
    fr: "Ces empreintes carbone correspondent à l'énergie grise des bâtiments.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RESULTS PAGE — CHARTS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // The results page contains several charts, each with optional (ℹ) icons on
  // their title or on the coloured filter badges above them. These give context
  // about what the chart shows or how a particular filter was calculated.

  'results-charts-it-focus-breakdown-title': {
    en: 'The carbon footprint considered here are those related to the purchase of IT equipment, the energy required for its use, and the use of services (internal or external) such as AI and cloud services.',
    fr: "Les empreintes carbone considérées ici sont celles liées à l'achat d'équipement informatique, à l'énergie nécessaire pour l'utiliser, et à l'usage des services (internes ou externes) tels que l'IA et les clouds externes.",
  },
  'results-charts-unit-trajectory-title': {
    en: 'Play around with the different reduction sliders to see if your unit can follow the EPFL objective trajectory.',
    fr: "Jouez avec les différents curseurs de réduction pour voir si votre unité peut suivre la trajectoire des objectifs de l'EPFL.",
  },
  'results-charts-embodied-energy-title': {
    en: 'This analysis only covers current constructions, renovations and demolitions; it does not include buildings constructed, renovated or demolished in other years. The actual footprint of EPFL buildings is higher.',
    fr: "Cette analyse ne concerne que les constructions, rénovations et démolitions en cours; elle n'inclut pas les bâtiments construits, rénovés ou démolis dans le passé. L'empreinte carbone réelle des bâtiments de l'EPFL est plus élevée.",
  },
  'results-charts-research-facilities-filter': {
    en: 'These carbon footprints are calculated based on research facilities data.',
    fr: 'Ces empreintes carbone sont calculées à partir des données propres aux infrastructure de recherche.',
  },
  'results-charts-additional-data-filter': {
    en: "These carbon footprints are calculated based on EPFL's general assumptions.",
    fr: "Ces empreintes carbone sont calculées à partir des hypothèses générales de l'EPFL.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RESULTS PAGE — REDUCTION OBJECTIVE SLIDERS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // The "reduction objective" section lets users drag sliders to simulate how
  // each emission category might evolve over time. A (ℹ) icon can appear next
  // to each slider label. Leave en/fr empty ("") to hide the icon.
  //
  // Slider order in the app:
  //   Process Emissions → Buildings (combustion) → Buildings (rooms) →
  //   Equipment → External Cloud & AI → Professional Travel → Purchases →
  //   Research Facilities → Commuting → Food → Waste → Embodied Energy

  'results-reduction-title': {
    en: 'This section presents two graphs. The first allows you to simulate the evolution of your unit carbon footprints and adjust each category in order to converge towards the net zero trajectory. The second illustrates the reference net zero trajectory for EPFL, aligned with the carbon footprint reduction targets set by the Swiss Confederation and the Climate Act.',
    fr: "Cette section présente deux graphiques. Le premier vous permet de simuler l'évolution des émissions de votre unité et d'ajuster chaque catégorie afin de converger vers la trajectoire net zéro. Le deuxième illustre la trajectoire net zéro de référence pour l'EPFL, alignée sur les objectifs de réduction des émissions de CO₂ fixés par la Confédération et la Loi Climat.",
  },
  'results-reduction-process_emissions': { en: '', fr: '' },
  'results-reduction-buildings_energy_combustion': { en: '', fr: '' },
  'results-reduction-buildings_room': { en: '', fr: '' },
  'results-reduction-equipment': {
    en: 'Low effort: switching oof unused equipment. Middle of the road: sharing equipment, optimize active/standby schedule. High effort: Widespread sharing, energy intensive equipments use optimized. Ambitious: Sharing and pooling across the institution, energy-intensive devices minimized. ',
    fr: 'Faible effort : éteindre les équipements inutilisés. Niveau intermédiaire : partager les équipements, optimiser les horaires de fonctionnement et de veille. Effort élévé: partage généralisé, utilisation optimisée des équipements à forte consommation d'énergie. Ambition : partage et mise en commun à l'échelle de l'établissement, réduction au minimum des appareils à forte consommation d'énergie.',
  },
  'results-reduction-external_cloud_and_ai': { en: '', fr: '' },
  'results-reduction-professional_travel': { en: '', fr: '' },
  'results-reduction-purchases': { en: '', fr: '' },
  'results-reduction-research_facilities': { en: '', fr: '' },
  'results-reduction-commuting': { en: '', fr: '' },
  'results-reduction-food': { en: '', fr: '' },
  'results-reduction-waste': { en: '', fr: '' },
  'results-reduction-embodied_energy': { en: '', fr: '' },

  // ═══════════════════════════════════════════════════════════════════════════
  // MODULE RESULTS — STAT CARD TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Each module has its own results section with stat cards
  // (e.g. "Total electricity use" for Equipment).
  // A (ℹ) icon can appear on each card to give extra context.

  'results-equipment-stats-total-electricity-use-title': {
    en: 'Total electricity consumption of all equipment in the unit',
    fr: "Consommation électrique totale de tous les équipements de l'unité",
  },
  'results-equipment-stats-share-of-lab-total-title': {
    en: "Percentage of the lab's total carbon footprint represented by equipment electricity consumption",
    fr: "Pourcentage de l'empreinte carbone totale du laboratoire représenté par la consommation électrique des équipements",
  },
  'results-equipment-stats-year-to-year-evolution-title': {
    en: 'Change in electricity consumption compared to the previous year',
    fr: "Évolution de la consommation électrique par rapport à l'année précédente",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // BACK-OFFICE TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Tooltips used in the administrator back-office pages (data management,
  // reporting). These are only visible to admin users, not to lab users.

  'backoffice-data-management-open-year-disabled': {
    en: 'All mandatory factor and reference uploads must be completed before opening the year for users.',
    fr: "Tous les téléversements obligatoires de facteurs et de références doivent être complétés avant d'ouvrir l'année pour les utilisateurs.",
  },
  'backoffice-data-management-year-already-open': {
    en: 'Year is already open to users',
    fr: "L'année est déjà ouverte aux utilisateurs",
  },
  'backoffice-reporting-completion-rate': {
    en: 'Each unit has equal weight, independent of FTE size',
    fr: 'Chaque unité a le même poids, indépendamment de la taille en EPT',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CO₂ PROJECT PLANNER — GRANT PROPOSAL SECTION
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // These tooltips appear ONLY inside the "Project Grant" section of a plan.
  // The project-year sections below have their own separate texts, and the
  // Calculator keeps the `module-…` texts further up in this file.

  'planner-project-info-section-title': {
    en: 'Select whether you want to estimate a project carbon footprint in line with a grant application and/ or for a past, ongoing, or future project.',
    fr: "Sélectionnez si vous voulez estimer l'empreinte d'un projet en lien avec une demande de financement et/ou pour un projet passé, en cours, ou futur.",
  },

  'planner-grant-proposal-title': {
    en: "This section allows you to gather information related to a research project’s carbon footprint as requested by funding agencies. Please contact co2calculator{'@'}epfl.ch if the agencies ask for information that you cannot find here.",
    fr: "Cette section vous permet de collecter les informations liées à l'empreinte carbone d'un projet de recherche demandées par les agences de financement. Merci de contacter co2calculator{'@'}epfl.ch si les agences vous demandent des informations que vous ne retrouvez pas ici.",
  },

  'planner-grant-section-title': {
    en: "Start completing the modules to obtain the carbon footprint estimate for a research project, as required by funding agencies. Please contact co2calculator{'@'}epfl.ch if the agencies ask you for information that you cannot find here.",
    fr: "Commencez à remplir les sections afin d'obtenir l'estimation de l'empreinte carbone d'un projet de recherche demandées par les agences de financement. Merci de contacter co2calculator{'@'}epfl.ch si les agences vous demandent des informations que vous ne retrouvez pas ici.",
  },

  'planner-grant-module-headcount-title': {
    en: 'This module automatically displays the main staff categories. Please verify or manually enter the total FTE for a project year. The total number of FTEs is used to generate indicators for additional categories (Scope 3: Food, Commuting, and Waste).',
    fr: "Ce module affiche automatiquement les grandes catégories de personnel. Veuillez vérifier ou ajouter manuellement les EPT total pour une année de projet. Le nombre total d'EPT est utilisé pour générer les indicateurs des catégories additionnelles (Scope 3 : Alimentation, Pendularité et Déchets).",
  },
  'planner-grant-module-headcount-submodule-member': {
    en: 'Please enter project members, including their role and activity percentage in the Full-Time Equivalent (FTE) field.',
    fr: "Veuillez saisir les membres avec leur fonction et pourcentage d'activité sous le champ équivalent plein-temps (EPT).",
  },

  'planner-grant-module-headcount-submodule-student': {
    en: 'Please enter the number of students in Full-Time Equivalents (FTE).',
    fr: "Veuillez saisir le nombre d'étudiantes et étudiants en équivalent plein-temps (EPT).",
  },

  'planner-grant-module-process-emissions-title': {
    en: 'This module helps you estimate greenhouse gas emissions from experimental procedures and equipment leaks as part of your project, such as CO₂ used in lab protocols, SF₆ leaks during etching, fluorinated gas leaks from refrigeration systems, or fluorinated ether evaporation during sample handling (Scope 1).',
    fr: "Ce module permet d'estimer les émissions de gaz à effet de serre liées à vos procédures expérimentales et aux fuites d’équipements dans le cadre de votre projet, par exemple : l'utilisation de CO₂ dans les protocoles de laboratoire, les fuites de SF₆ lors de la gravure, les fuites de gaz fluorés des systèmes de réfrigération, ou l’évaporation d’éthers fluorés pendant la manipulation des échantillons (Scope 1).",
  },
  'planner-grant-module-process-emissions-submodule-process_emissions': {
    en: 'Please note that the budget associated with your unit’s process emissions is, in most cases, zero. Indeed, these emissions are either included in your purchases, in which case the corresponding budget should be allocated to the purchases category, or funded by central services, in which case they do not fall within your unit scope.',
    fr: 'Veuillez noter que le budget associé aux émissions de procédés de votre unité est, dans la plupart des cas, égal à zéro. En effet, ces émissions sont soit incluses dans vos achats, et leur budget doit alors être comptabilisé dans cette catégorie, soit financées par les services centraux, auquel cas elles ne font pas partie du périmètre de votre unité.',
  },

  'planner-grant-module-buildings-title': {
    en: 'This module allows you to estimate the carbon footprint associated with buildings if your unit uses a decentralized energy source (emissions from energy combustion) (Scope 1), as well as those associated with the rooms (Scope 2: heating, cooling, ventilation, and lighting) specific to your project.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux Bâtiments dans le cas où votre unité utilise une source d'énergie non-centralisée (émissions de combustion d'énergie) (Scope 1) ainsi que celles liées aux locaux (Scope 2: chauffage, climatisation, ventilation et éclairage) spécifique à votre projet.",
  },
  'planner-grant-module-buildings-submodule-building': {
    en: 'Please specify the use of each room in the table to estimate its carbon footprint as part of your project (Scope 2). You can enter the percentage of the reference year or manually add a room.',
    fr: "Veuillez indiquer l'utilisation des locaux dans le tableau afin d'estimer leur empreinte carbone dans le cadre de votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement un local. ",
  },
  'planner-grant-module-buildings-submodule-energy_combustion': {
    en: 'Please select from the list the combustion source(s) (fossil or non-fossil) specific to your project in order to estimate their carbon footprint (Scope 1).',
    fr: "Veuillez sélectionner dans la liste la ou les sources de combustion (fossiles ou non fossiles) spécifique à votre projet afin d'estimer leur empreinte carbone (Scope 1).",
  },

  'planner-grant-module-equipment-title': {
    en: 'This module allows you to estimate the carbon footprint associated with the electricity consumption of equipment (scientific equipment, IT equipment, other equipment) specific to your project (Scope 2).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à la consommation électrique des équipements (Équipements scientifiques, Équipements IT, Autres équipements) spécifique à votre projet (Scope 2).",
  },
  'planner-grant-module-equipment-submodule-scientific': {
    en: 'Indicate the scientific equipment used to estimate its carbon footprint specific to your project (Scope 2). You can specify the percentage of the reference year or manually add an equipment.',
    fr: "Indiquez les équipements scientifiques utilisés afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement un équipement.",
  },
  'planner-grant-module-equipment-submodule-it': {
    en: 'Indicate the IT equipment used to estimate its carbon footprint specific to your project (Scope 2). You can specify the percentage of the reference year or manually add an equipment.',
    fr: "Indiquez les équipements informatiques utilisés afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement un équipement. ",
  },
  'planner-grant-module-equipment-submodule-other': {
    en: 'Indicate other types of equipment used to estimate their carbon footprint specific to your project (Scope 2). You can specify the percentage of the reference year or manually add a piece of equipment.',
    fr: "Indiquez les autres types d' équipements utilisés afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement un équipement. ",
  },

  'planner-grant-module-external-cloud-and-ai-title': {
    en: 'This module allows you to estimate the carbon footprint associated with external cloud services and external AIs specific to your project (Scope 3).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux services de clouds externes et d'IAs externes spécifique à votre projet (Scope 3).",
  },
  'planner-grant-module-external-cloud-and-ai-submodule-external_clouds': {
    en: 'Indicate the use of external cloud services in order to estimate their impact within your project (Scope 3). You can specify the percentage of the reference year or manually add an external cloud service.',
    fr: "Indiquez l'utilisation des services de clouds externes  afin d'estimer leur impact dans le cadre de votre projet (Scope 3). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement le service de cloud externes.",
  },
  'planner-grant-module-external-cloud-and-ai-submodule-external_ai': {
    en: 'Indicate the use of external AI services in order to estimate their impact within your project (Scope 3). You can specify the percentage of the reference year or manually enter the IA used.',
    fr: " Indiquez l'utilisation des services d'IAs  externes  afin d'estimer leur impact dans le cadre de votre projet (Scope 3). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement l'IA utilisé. ",
  },

  'planner-grant-module-professional-travel-title': {
    en: 'This module allows you to estimate the carbon footprint associated with professional travel by plane and/or train specific to your project (Scope 3).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux voyages professionnels effectués en avion et/ou en train spécifique à votre projet (Scope 3).",
  },
  'planner-grant-module-professional-travel-submodule-plane': {
    en: 'Add the flights planned within the scope of your project to estimate their associated impact for the reference year (Scope 3).',
    fr: "Ajoutez vos trajets en avion spécifique à votre projet afin d'estimer leur impact (Scope 3). ",
  },
  'planner-grant-module-professional-travel-submodule-train': {
    en: 'Add the train journeys planned within the scope of your project to estimate their associated impact for the reference year (Scope 3).',
    fr: "Ajoutez vos trajets en avion spécifique à votre projet afin d'estimer leur impact (Scope 3). ",
  },

  'planner-grant-module-purchase-title': {
    en: 'This module allows you to estimate the carbon footprint associated with project-specific purchases (Scope 3). To do so, please indicate the budget allocated to the relevant purchasing categories (Scientific Equipment, IT Equipment, Consumables and Accessories, Biological, Chemical and Gas Products, Services, Vehicles, and Other Purchases).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux achats spécifiques à votre projet (Scope 3). Pour cela, veuillez indiquer le budget correspondant aux catégories d'achats (Équipements scientifiques, Équipements informatiques, Consommables et accessoires, Produits biologiques, chimiques et gazeux, Services, Véhicules, Autres achats).",
  },
  'planner-grant-module-purchase-submodule-scientific_equipment': {
    en: '',
    fr: '',
  },
  'planner-grant-module-purchase-submodule-it_equipment': { en: '', fr: '' },
  'planner-grant-module-purchase-submodule-consumable_accessories': {
    en: '',
    fr: '',
  },
  'planner-grant-module-purchase-submodule-biological_chemical_gaseous_product':
    { en: '', fr: '' },
  'planner-grant-module-purchase-submodule-services': { en: '', fr: '' },
  'planner-grant-module-purchase-submodule-vehicles': { en: '', fr: '' },
  'planner-grant-module-purchase-submodule-other_purchases': {
    en: '',
    fr: '',
  },
  'planner-grant-module-purchase-submodule-purchases_centralized': {
    en: '',
    fr: '',
  },

  'planner-grant-module-research-facilities-title': {
    en: 'This module allows you to estimate the carbon footprint associated with the use of EPFL research infrastructures specific to your project (Scope 3). To do so, add the relevant research infrastructures and animal facilities, indicating the corresponding budget for each.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à l'utilisation des infrastructures de recherche EPFL spécifiques à votre projet (Scope 3). Pour cela, ajoutez les infrastructures de recherche et animaleries en indiquant le budget correspondant.",
  },
  'planner-grant-module-research-facilities-submodule-research-facilities': {
    en: '',
    fr: '',
  },
  'planner-grant-module-research-facilities-submodule-animal_facilities': {
    en: '',
    fr: '',
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CO₂ PROJECT PLANNER — PROJECT YEAR SECTIONS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // These tooltips appear inside each project-year section of a plan (the
  // sections titled with a year), where the figures come from the Calculator
  // data of that year.

  'planner-year-section-title': {
    en: 'View and complete the estimated carbon impact data by project year here. This data comes from the CO₂ calculator.\n\nIf you would like to grant access to this space to other members of your unit, please assign them the Primary User role in the EPFL accreditation system: https://accred.epfl.ch/.',
    fr: "Retrouvez et complétez ici les données d'impact carbone estimé par année de projet. Ces données remontent de l'espace calculateur CO₂.\n\n Si vous voulez donner accès à cet espace à d'autres membres de votre unité, veuillez les accréditer comme Utilisateur Principal dans https://accred.epfl.ch/.",
  },

  'planner-year-module-headcount-title': {
    en: 'This module automatically displays the main personnel categories. Please verify or manually add the total FTE by project year. The total number of FTE is used to generate indicators for the additional categories (Scope 3: Food, Commuting, and Waste).',
    fr: "Ce module affiche automatiquement les grandes catégories de personnel. Veuillez vérifier ou ajouter manuellement les EPT total par année de projet. Le nombre total d'EPT est utilisé pour générer les indicateurs des catégories additionnelles (Scope 3: Alimentation, Pendularité et Déchets).",
  },
  'planner-year-module-headcount-submodule-member': {
    en: 'Please enter the percentage of team members involved in the project, along with their role and percentage of effort under the Full-Time Equivalent (FTE) field.',
    fr: "Veuillez saisir le pourcentage des  membres impliqué dans le projet avec leur fonction et pourcentage d'activité sous le champ Équivalent plein-temps (EPT).",
  },

  'planner-year-module-headcount-submodule-student': {
    en: 'Please enter the percentage of students involved in the project in terms of Full-Time Equivalent (FTE) field.',
    fr: 'Veuillez saisir  le pourcentage des étudiantes et étudiants impliqués dans le projet en Équivalent plein-temps (EPT).',
  },

  'planner-year-module-process-emissions-title': {
    en: 'This module helps you estimate greenhouse gas emissions from experimental procedures and equipment leaks, such as CO₂ used in lab protocols, SF₆ leaks during etching, fluorinated gas leaks from refrigeration systems, or fluorinated ether evaporation during sample handling (Scope 1).',
    fr: "Ce module petmet d'estimer les émissions de gaz à effet de serre liées à vos procédures expérimentales et aux fuites d’équipements, par exemple : l'utilisation de CO₂ dans les protocoles de laboratoire, les fuites de SF₆ lors de la gravure, les fuites de gaz fluorés des systèmes de réfrigération, ou l’évaporation d’éthers fluorés pendant la manipulation des échantillons (Scope 1).",
  },

  'planner-year-module-buildings-title': {
    en: 'This module allows you to estimate the carbon footprint associated with buildings (emissions from energy combustion and rooms) if your unit uses a decentralized energy source (Scope 1), as well as emissions associated with the rooms (Scope 2: heating, cooling, ventilation, and lighting) specific to your project.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux Bâtiments (émissions de combustion d'énergie et locaux) dans le cas où votre unité utilise une source d'énergie non-centralisée (Scope 1) ainsi que celles liées aux locaux (Scope 2: chauffage, climatisation, ventilation et éclairage) spécifique à votre projet.",
  },
  'planner-year-module-buildings-submodule-building': {
    en: 'Please specify the use of each room in the table to estimate its carbon footprint specific to your project (Scope 2). You can enter the percentage of the reference year or manually add a room.',
    fr: "Veuillez indiquer l'utilisation des locaux dans le tableau afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence ou ajouter manuellement un local. ",
  },
  'planner-year-module-buildings-submodule-energy_combustion': {
    en: 'Please select from the list the combustive sources (fossil or non-fossil) specific to your project in order to estimate their carbon footprint (Scope 1).',
    fr: "Veuillez sélectionner dans la liste la ou les sources de combustion (fossiles ou non fossiles) spécifique à votre projet afin d'estimer leur empreinte carbone (Scope 1). ",
  },

  'planner-year-module-equipment-title': {
    en: 'This module allows you to estimate the carbon footprint associated with the electricity consumption of equipment used specifically for your project (Scientific Equipment, IT Equipment, and Other Equipment) (Scope 2).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à la consommation électrique des équipements (Équipements scientifiques, Équipements IT, Autres équipements) spécifique à votre projet (Scope 2).",
  },
  'planner-year-module-equipment-submodule-scientific': {
    en: 'Indicate the scientific equipment used to estimate its carbon footprint specific to your project (Scope 2). You can enter the percentage of the reference year in the table or manually add an equipment.',
    fr: "Indiquez les équipements scientifiques utilisés afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence dans le tableau ou ajouter manuellement un équipement. ",
  },
  'planner-year-module-equipment-submodule-it': {
    en: 'Indicate the IT equipment used to estimate its carbon footprint specific to your project (Scope 2). You can enter the percentage of the reference year in the table or manually add an equipment.',
    fr: "Indiquez les équipements informatiques utilisés afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence dans le tableau ou ajouter manuellement un équipement.",
  },
  'planner-year-module-equipment-submodule-other': {
    en: 'Indicate other types of equipment used to estimate their carbon footprint specific to your project (Scope 2). You can enter the percentage of the reference year in the table or manually add an equipment.',
    fr: "Indiquez les autres types d' équipements  utilisés afin d'estimer leur empreinte carbone  spécifique à votre projet (Scope 2). Vous pouvez indiquer le % de l'année de référence dans le tableau ou ajouter manuellement un équipement.",
  },

  'planner-year-module-external-cloud-and-ai-title': {
    en: 'This module allows you to estimate the carbon footprint associated with external cloud services and external AI services used specifically for your project (Scope 3).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux services de clouds externes et d'IAs externes spécifique à votre projet (Scope 3).",
  },
  'planner-year-module-external-cloud-and-ai-submodule-external_clouds': {
    en: ' Specify your use of external cloud services to estimate their carbon footprint specific to your project (Scope 3). You can enter the percentage of the reference year in the table or manually add the external cloud service.',
    fr: " Indiquez l'utilisation des services de clouds externes  afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 3). Vous pouvez indiquer le % de l'année de référence dans le tableau ou ajouter manuellement le service de cloud externes. ",
  },
  'planner-year-module-external-cloud-and-ai-submodule-external_ai': {
    en: 'Indicate your use of external AI services to estimate their carbon footprint as part of your project (Scope 3). You can enter the percentage of the reference year in the table or manually add the AI service used.',
    fr: "Indiquez l'utilisation des services d'IAs  externes  afin d'estimer leur empreinte carbone dans le cadre de votre projet (Scope 3). Vous pouvez indiquer le % de l'année de référence dans le tableau ou ajouter manuellement le service d'IA utilisé.",
  },

  'planner-year-module-professional-travel-title': {
    en: 'This module allows you to estimate the carbon footprint associated with professional travel (plane and/or train) specific to your project (Scope 3).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux voyages professionnels (en avion et/ou en train) spécifique à votre projet (Scope 3).",
  },
  'planner-year-module-professional-travel-submodule-plane': {
    en: 'Review your plane trips within the unit. You can manually add additional trips or delete trips that are not part of the project.',
    fr: "Visualiser vos voyages en avion au sein de l'unité. Vous pouvez ajouter manuellement d'autres voyages ou supprimer les voyages qui ne sont pas effectués dans le cadre du projet.",
  },
  'planner-year-module-professional-travel-submodule-train': {
    en: 'Review your train trips within the unit. You can manually add additional trips or delete trips that are not part of the project.',
    fr: "Visualiser vos voyages en train au sein de l'unité. Vous pouvez ajouter manuellement d'autres voyages ou supprimer les voyages qui ne sont pas effectués dans le cadre du projet.",
  },

  'planner-year-module-purchase-title': {
    en: 'This module allows you to estimate the carbon footprint associated with project-specific purchases (Scope 3). To do so, please indicate the budget allocated to the relevant purchasing categories (Scientific Equipment, IT Equipment, Consumables and Accessories, Biological, Chemical and Gas Products, Services, Vehicles, and Other Purchases).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux achats spécifiques à votre projet (Scope 3). Pour cela, veuillez indiquer le budget correspondant aux catégories d'achats (Équipements scientifiques, Équipements informatiques, Consommables et accessoires, Produits biologiques, chimiques et gazeux, Services, Véhicules, Autres achats).",
  },
  'planner-year-module-purchase-submodule-scientific_equipment': {
    en: '',
    fr: '',
  },
  'planner-year-module-purchase-submodule-it_equipment': { en: '', fr: '' },
  'planner-year-module-purchase-submodule-consumable_accessories': {
    en: '',
    fr: '',
  },
  'planner-year-module-purchase-submodule-biological_chemical_gaseous_product':
    { en: '', fr: '' },
  'planner-year-module-purchase-submodule-services': { en: '', fr: '' },
  'planner-year-module-purchase-submodule-vehicles': { en: '', fr: '' },
  'planner-year-module-purchase-submodule-other_purchases': { en: '', fr: '' },
  'planner-year-module-purchase-submodule-purchases_centralized': {
    en: '',
    fr: '',
  },

  'planner-year-module-research-facilities-title': {
    en: 'This module allows you to estimate the carbon footprint associated with the use of EPFL research facilities specific to your project (Scope 3).',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à l'utilisation des infrastructures de recherche EPFL spécifiques à votre projet (Scope 3).",
  },
  'planner-year-module-research-facilities-submodule-research-facilities': {
    en: 'Indicate the use of research infrastructure to estimate its carbon footprint specific to your project (Scope 3). You can enter the percentage of use based on the reference year in the table.',
    fr: "Indiquez l'utilisation des infrastructures de recherche afin d'estimer leur empreinte carbone spécifique à votre projet (Scope 3). Vous pouvez indiquer le % d'utilisation selon  l'année de référence dans le tableau.",
  },
  'planner-year-module-research-facilities-submodule-animal_facilities': {
    en: 'Indicate the use of animal facilities to estimate their carbon footprint specific to your project (Scope 3). You can indicate the percentage of use relative to the reference year in the table.',
    fr: " Indiquez l'utilisation des animaleries e afin d'estimer leur empreinte carbone spécifique à  votre projet (Scope 3). Vous pouvez indiquer le % d'utilisation selon l'année de référence dans le tableau.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CO₂ EXPLORER
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // These tooltips appear only on the CO₂ Explorer page, next to each module
  // and sub-module title.

  'explorer-module-headcount-title': {
    en: 'This module uses headcount data to generate indicators for additional categories (Food, Commuting, and Waste) (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: 'Ce module considère les données du personnel afin de générer les indicateurs des catégories additionnelles (Alimentation, Pendularité et Déchets) (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.',
  },
  'explorer-module-headcount-submodule-member': {
    en: 'Members sub-module: Please enter project members, including their role and activity percentage in the Full-Time Equivalent (FTE) field.',
    fr: "Sous-module Membre : Veuillez saisir les membres avec leur fonction et pourcentage d'activité sous le champ Équivalent plein-temps (EPT).",
  },
  'explorer-module-headcount-submodule-student': {
    en: 'Students sub-module: Please enter the number of students in Full-Time Equivalents (FTE).',
    fr: 'Sous-module Étudiant.es : Veuillez saisir le nombre d’étudiantes et étudiants en Équivalent plein-temps (EPT).',
  },

  'explorer-module-process-emissions-title': {
    en: 'This module helps you estimate greenhouse gas emissions from experimental procedures and equipment leaks, such as CO₂ used in lab protocols, SF₆ leaks during etching, fluorinated gas leaks from refrigeration systems, or fluorinated ether evaporation during sample handling (Scope 1). \n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l’empreinte carbone des gaz à effet de serre générés lors de vos activités de laboratoire spécifique à votre projet  (e.g. émissions de CO₂ Scope 1 dans certaines activités de laboratoire, émissions de SF₆ quand celui-ci est utilisé en tant que fluide frigorigène). \n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-process-emissions-submodule-process_emissions': {
    en: '',
    fr: '',
  },

  'explorer-module-buildings-title': {
    en: 'This module allows you to explore the carbon footprint associated with buildings (energy combustion emissions and rooms) (Scopes 1 and 2) specific to your project.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée aux Bâtiments (émissions de combustion d'énergie et locaux) (Scope 1 et 2) spécifique à votre projet.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-buildings-submodule-building': {
    en: 'Explore the carbon footprint associated with the use of certain rooms. To get started, select a building from the drop-down list.',
    fr: "Explorez l'empreinte carbone liée à l'utilisation de certains locaux. Pour commencer, sélectionner un bâtiment dans la liste déroulante.",
  },
  'explorer-module-buildings-submodule-energy_combustion': {
    en: 'Explore the carbon footprint associated with energy combustion emissions. To get started, select the combustion source(s) (fossil or non-fossil) from the list to estimate their impact (Scope 1).',
    fr: "Explorez l'empreinte carbone liée aux émissions de combustion d'énergie. Pour commencer, sélectionnez dans la liste la ou les sources de combustion (fossiles ou non fossiles) afin d'estimer leur impact (Scope 1).",
  },

  'explorer-module-equipment-title': {
    en: 'This module allows you to explore the carbon footprint associated with the electricity consumption of equipment (Scientific Equipment, IT Equipment, and Other Equipment) (Scope 2).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée à la consommation électrique des équipements (Équipements scientifiques, Équipements IT, Autres équipements) (Scope 2).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-equipment-submodule-scientific': {
    en: 'Explore the carbon footprint of a scientific equipment item. To get started, please select a class.',
    fr: "Explorez l'empreinte carbone d'un équipement scientifique. Pour commencer, veuillez sélectionner une classe.",
  },
  'explorer-module-equipment-submodule-it': {
    en: 'Explore the carbon footprint of an IT equipment item. To get started, please select a class.',
    fr: "Explorez l'empreinte carbone d'un équipement IT. Pour commencer, veuillez sélectionner une classe.",
  },
  'explorer-module-equipment-submodule-other': {
    en: 'Explore the carbon footprint of another type of equipment. To get started, please select a class.',
    fr: "Explorez l'empreinte carbone d'un autre type d'équipement. Pour commencer, veuillez sélectionner une classe.",
  },

  'explorer-module-external-cloud-and-ai-title': {
    en: 'This module allows you to explore the carbon footprint associated with the use of external cloud services and external AI services (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée à l'utilisation des services de clouds externes et d'IAs externes (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-external-cloud-and-ai-submodule-external_clouds': {
    en: 'Explore the carbon footprint of an external cloud service.',
    fr: "Explorez l'empreinte carbone d'un service de clouds externes.",
  },
  'explorer-module-external-cloud-and-ai-submodule-external_ai': {
    en: 'Explore the carbon footprint of an external AI service.',
    fr: "Explorez l'empreinte carbone d'un service d'IAs externes.",
  },

  'explorer-module-professional-travel-title': {
    en: 'This module allows you to explore the carbon footprint associated with professional travel (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée aux voyages professionnels (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-professional-travel-submodule-plane': {
    en: 'Explore the carbon footprint of a professional flight.',
    fr: "Explorez l'empreinte carbone d'un voyage professionnel en avion.",
  },
  'explorer-module-professional-travel-submodule-train': {
    en: 'Explore the carbon footprint of a professional train journey.',
    fr: "Explorez l'empreinte carbone d'un voyage professionnel en train.",
  },

  'explorer-module-purchase-title': {
    en: 'This module allows you to explore the carbon footprint associated with purchases across the following categories: Scientific Equipment, IT Equipment, Consumables and Accessories, Biological, Chemical and Gas Products, Services, Vehicles, Other Purchases, and Centralized Purchases (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée aux achats selon les catégories suivantes : Équipements scientifiques, Équipements informatiques, Consommables et accessoires, Produits biologiques, chimiques et gazeux, Services, Véhicules, Autres achats et Achats centralisés (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-scientific_equipment': {
    en: 'Explore the carbon footprint associated with the purchase of scientific equipment according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone de l'achat d'un équipement scientifique selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-it_equipment': {
    en: 'Explore the carbon footprint associated with the purchase of IT equipment according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone de l'achat d'un équipement informatique selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-consumable_accessories': {
    en: 'Explore the carbon footprint associated with the purchase of consumables and accessories according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone de l'achat d'un consommable et accessoire selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-biological_chemical_gaseous_product': {
    en: 'Explore the carbon footprint associated with the purchase of biological, chemical, and gas products according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone de l'achat d'un produit biologique, chimique et gazeux selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-services': {
    en: 'Explore the carbon footprint associated with the purchase of a service according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone de l'achat d'un service selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-vehicles': {
    en: 'Explore the carbon footprint associated with the purchase of a vehicle according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone de l'achat d'un véhicule selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-other_purchases': {
    en: 'Explore the carbon footprint associated with other purchases according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone d'un achat de type autre selon la classification UNSPSC.",
  },
  'explorer-module-purchase-submodule-purchases_centralized': {
    en: 'Explore the carbon footprint associated with a centralized purchase according to the UNSPSC classification.',
    fr: "Explorez l'empreinte carbone d'un achat centralisé selon la classification UNSPSC.",
  },

  'explorer-module-research-facilities-title': {
    en: 'This module allows you to explore the carbon footprint associated with the use of EPFL research facilities (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée à l'utilisation des infrastructures de recherche EPFL (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-research-facilities-submodule-research-facilities': {
    en: 'Explore the carbon footprint associated with the use of a research facility. Please enter the corresponding budget and/or number of usage hours depending on the facility.',
    fr: "Explorez l'empreinte carbone liée à l'utilisation d'une infrastructure de recherche. Veuillez rentrer un budget et/ou des heures d'utilisation selon l'infrastructure.",
  },
  'explorer-module-research-facilities-submodule-animal_facilities': {
    en: 'Explore the carbon footprint associated with the use of an animal facility. Please enter the number of housing units for rodents and fish.',
    fr: "Explorez l'empreinte carbone liée à l'utilisation d'une animalerie. Veuillez rentrer un nombre d'hébergements pour les rongeurs et poissons.",
  },

  documentation_editing_rows_tooltips_topic: {
    en: 'Tooltips',
    fr: 'Info-bulles',
  },
  documentation_editing_rows_tooltips_description: {
    en: 'Find all tooltip texts shown as (ℹ) icons throughout the application.',
    fr: "Trouvez tous les textes des info-bulles affichées sous forme d'icônes (ℹ) dans l'application.",
  },
} as const;
