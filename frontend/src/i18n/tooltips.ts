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
    en: "The emissions calculated by this Headcount module contribute to Scope 3 of the unit's carbon footprint.",
    fr: "Les émissions déterminées par ce module Personnel contribuent au Scope 3 de l'empreinte carbone de l'unité.",
  },
  'module-process-emissions-title': {
    en: 'The emissions from the Process emissions module contribute to Scope 1 of the laboratory’s carbon footprint.',
    fr: "Les émissions du module Emissions de procédés contribue au Scope 1 de l'empreinte carbone du laboratoire.",
  },
  'module-buildings-title': {
    en: 'Emissions from the Buildings module contribute to Scope 1 (on-site energy combustion; for example, a natural gas boiler) and Scope 2 (electricity consumption for heating, cooling, ventilation, and lighting).',
    fr: 'Les émissions provenant du module Bâtiments contribuent aux scopes 1 (combustion d’énergie sur site; par exemple une chaudière à gaz naturel) et scope 2 ( consommation d’électricité pour le chauffage, le refroidissement, la ventilation et l’éclairage).'
  },
  'module-equipment-title': {
    en: "The emissions from the equipment module contribute to Scope 2 of the laboratory's carbon footprint.",
    fr: "Les émissions du module équipement contribue au scope 2 de l'empreinte carbone du laboratoire.",
  },
  'module-external-cloud-and-ai-title': {
    en: 'The emissions from the External clouds and AI module contribute to Scope 3 of the laboratory’s carbon footprint.',
    fr: "Les émissions du module Clouds externes et IA contribue au scope 3 de l'empreinte carbone du laboratoire.",
  },
  'module-professional-travel-title': {
    en: 'The emissions from the Professional travel module contribute to Scope 3 of the laboratory’s carbon footprint.',
    fr: "Les émissions du module Voyages professionels contribue au scope 3 de l'empreinte carbone du laboratoire."
  },
  'module-purchase-title': {
    en: 'The emissions from the Purchases module contribute to Scope 3 of the laboratory’s carbon footprint.',
    fr: "Les émissions du module Achats contribue au scope 3 de l'empreinte carbone du laboratoire."
  },
  'module-research-facilities-title': {
    en: 'The methodology used to calculate the carbon footprint of research facilities is documented in the Documentation pages',
    fr: "La méthodologie utilisée pour calculer de l'empreinte carbone des infrastructures de recherche est documentée dans les pages Documentation",
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
    en: '',
    fr: '',
  },
  'module-headcount-submodule-student': {
    en: 'Due to data-protection rules, students names and individual FTE are not shown automatically.',
    fr: 'En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement.',
  },

  // ── Process Emissions ──────────────────────────────────────────────────────
  'module-process-emissions-submodule-process_emissions': { en: '', fr: '' },

  // ── Buildings ──────────────────────────────────────────────────────────────
  'module-buildings-submodule-building': {
    en: 'Rooms surfaces are extracted from Archibus and energy consumption data per type of surface are provided by the VPO based on building-specific measurements.',
    fr: "Les surfaces des locaux sont extraites d'Archibus et les données de consommation énergétique par type de surface sont fournies par la VPO sur la base de mesures spécifiques aux bâtiments EPFL.",
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
  'module-external-cloud-and-ai-submodule-external_clouds': { en: '', fr: '' },
  'module-external-cloud-and-ai-submodule-external_ai': { en: '', fr: '' },

  // ── Professional Travel ────────────────────────────────────────────────────
  'module-professional-travel-submodule-plane': {
    en: 'The flights listed in the table are provided by the EPFL Central Travel Agency. If any flights are missing, you can add them manually.',
    fr: "Les vols affichés dans le tableau proviennent de l'agence de voyage central EPFL. S'il manque des vols, il est possible de les saisir manuellement."
  },
  'module-professional-travel-submodule-train': {
    en: 'Enter your train trips manually, whether they were taken in Switzerland or abroad. ',
    fr: "Saisissez manuellement les voyages effectués en train qu'ils soient en Suisse ou à l'étranger."
  },

  // ── Purchases ──────────────────────────────────────────────────────────────
  'module-purchase-submodule-scientific_equipment': {
    en: 'This table lists purchases that are automatically categorized as scientific equipment based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: "Ce tableau regroupe les achats automatiquement catégorisés comme équipements scientifiques selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).",
  },
  'module-purchase-submodule-it_equipment': {
    en: 'This table lists purchases that are automatically categorized as IT equipment based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse). For this category, EPFL-specific emission factors are used.',
    fr: "Ce tableau regroupe les achats automatiquement catégorisés comme équipements informatiques selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse). Pour cette catégorie, les facteurs d'émission spécifiques à l'EPFL sont utilisés."
  },
  'module-purchase-submodule-consumable_accessories': {
    en: 'This table lists purchases that are automatically categorized as consumables and accessories based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme consommables et accessoires selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).'
  },
  'module-purchase-submodule-biological_chemical_gaseous_product': {
    en: 'This table lists purchases that are automatically categorized as biological, chemical et gaseous products based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme produits biologiques chimiques et gazeux  selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).',
  },
  'module-purchase-submodule-services': {
    en: 'This table lists purchases that are automatically categorized as services based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme services selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).'
  },
  'module-purchase-submodule-vehicles': {
    en: 'This table lists purchases that are automatically categorized as vehicles based on the UNSPSC classification code selected when the order was placed (e.g., via Catalyse).',
    fr: 'Ce tableau regroupe les achats automatiquement catégorisés comme véhicules selon le code de classification UNSPSC choisi  lors de la commande (ex. via Catalyse).'
  },
  'module-purchase-submodule-other_purchases': {
    en: 'This table lists all remaining purchases whose classification codes do not correspond to any of the specific main categories.',
    fr: 'Ce tableau regroupe tous les achats restants dont les codes de classification ne correspondent à aucune des catégories principales spécifiques.'
  },
  'module-purchase-submodule-additional_purchases': {
    en: 'Enter annual consumption values if your unit uses any of the items listed below.',
    fr: 'Saisissez les consommations annuelles si votre unité utilise les éléments listés ci-dessous.',
  },

  // ── Research Facilities ────────────────────────────────────────────────────
  'module-research-facilities-submodule-research-facilities': {
    en: 'Emissions from research facilities allocated to the units are calculated based on Process emission, Energy combustion, Building, Equipment, and Purchases emissions, using billing or the number of hours used by your unit as the allocation key. If one or several research facilities are missing in the tool, do not hesitate to contact us so that we can provide you with more details.',
    fr: "Les émissions des infrastructures de recherche attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Combustion d'énergie, Bâtiments, Équipements et Achats en considérant comme clé de répartition les facturations ou le nombre d'heures d'utilisation de votre unité. Si une ou plusieurs infrastructures de recherche manquent dans l'outil, n'hésitez pas à nous contacter afin que nous puissions vous fournir plus de détails.",
  },
  'module-research-facilities-submodule-mice_and_fish_animal_facilities': {
    en: 'Emissions from the mice and fish facilities are allocated to individual units based on their use of housing units (e.g., cages and aquariums) throughout the year. These emissions are calculated based on the Process emissions, Buildings, Equipment, and Purchases, with the annual number of housing units serving as the allocation key.',
    fr: "Les émissions des animaleries rongeurs et poissons attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Bâtiments, Équipements et Achats en considérant comme clé de répartition le nombre d’hébergements (cages, aquariums) par année.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // DATA-ENTRY FORM TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // When a user opens the form to add or edit a row, a (ℹ) icon can appear
  // at the top of that form. The text below is what they see when they click it.
  // Leave en/fr empty ("") to hide the icon for that form.

  // ── Headcount ──────────────────────────────────────────────────────────────
  'module-headcount-submodule-member-form': { en: '', fr: '' },
  'module-headcount-submodule-student-form': {
    en: "Enter the total number of FTE of students who worked in your unit over the year",
    fr: "Saisissez le total des EPT des étudiant·es ayant travaillé dans votre unité sur l'année",
  },

  // ── Process Emissions ──────────────────────────────────────────────────────
  'module-process-emissions-submodule-process_emissions-form': {
    en: "Add your unit's process emissions to the list above, if any. The quantity of each greenhouse gas emitted must be estimated before entering the value into the calculator (e.g., taking into account that only X% of the SF₆ used is ultimately emitted).",
    fr: "Veuillez ajouter les émissions de procédés de votre unité dans la liste ci-dessous s'il y en a. La quantité de chaque gaz à effet de serre émise doit être estimée avant de saisir la valeur dans le calculateur (par ex. en prenant en compte que seulement X % du SF₆ utilisé est finalement émis).",
  },

  // ── Buildings ──────────────────────────────────────────────────────────────
  'module-buildings-submodule-building-form': {
    en: 'Please add any missing premises to the list above. Note that you will need to carry over this change during your next update of Archibus, as this is not done automatically through the CO₂ Calculator.',
    fr: "Veuillez ajouter les locaux qui manquent dans la liste ci-dessus. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour d'Archibus, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂."
  },
  'module-buildings-submodule-energy_combustion-form': {
    en: 'Enter the sources of fossil or non-fossil energy combustion if they are not taken into account in the main module.',
    fr: "Entrez les sources de combustion d'énergie fossiles ou non-fossiles si celles-ci ne sont pas prises en compte dans le module principal.",
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
    en: 'The provider, type of service used (currently available: computing or storage service), spending and its associated currency must be specified. To make it easier to enter information, you can fill out a CSV file in advance and upload it.',
    fr: 'Il faut spécifier le fournisseur, le type de service utilisé (disponible actuellement: service de calcul ou stockage) ainsi que le montant dépensé et la devise associée. Pour faciliter la saisie des informations, un fichier csv peut être préalablement rempli et uploadé.',
  },
  'module-external-cloud-and-ai-submodule-external_ai-form': { en: '', fr: '' },

  // ── Professional Travel ────────────────────────────────────────────────────
  'module-professional-travel-submodule-plane-form': {
    en: 'Each leg of the trip must be entered as a separate trip. For example, for a flight departing from Geneva and arriving in Los Angeles with a layover in Amsterdam: Geneva-Amsterdam, Amsterdam-Los Angeles.',
    fr: "Chaque étape du trajet doit être saisie comme un déplacement distinct. Par exemple, pour un vol au départ de Genève à destination de Los Angeles avec une escale à Amsterdam : Genève-Amsterdam, Amsterdam-Los-Angeles.",
  },
  'module-professional-travel-submodule-train-form': {
    en: 'Each leg of the trip must be entered as a separate trip. For example, for a train trip from Lausanne to Mannheim: Lausanne–Bern, Bern–Basel, Basel–Mannheim.',
    fr: "Chaque étape du trajet doit être saisie comme un déplacement distinct. Par exemple, pour un trajet en train  au départ de Lausanne à destination de Mannheim  : Lausanne-Berne, Berne-Bale, Bale-Mannheim.",
  },

  // ── Purchases ──────────────────────────────────────────────────────────────
  'module-purchase-submodule-scientific_equipment-form': { en: '', fr: '' },
  'module-purchase-submodule-it_equipment-form': { en: '', fr: '' },
  'module-purchase-submodule-consumable_accessories-form': { en: '', fr: '' },
  'module-purchase-submodule-biological_chemical_gaseous_product-form': {
    en: '',
    fr: '',
  },
  'module-purchase-submodule-services-form': { en: '', fr: '' },
  'module-purchase-submodule-vehicles-form': {
    en: "Enter any vehicle-related purchases paid with unit's credit card here (e.g. fuel, car rentals, tolls, parking, or vehicle maintenance).",
    fr: "Veuillez ajouter tous les achats liés aux véhicules réglés avec la carte de crédit de l'unité (ex. le carburant, les locations de voiture, les péages, les frais de stationnement ou l'entretien des véhicules."
  },
  'module-purchase-submodule-other_purchases-form': { en: '', fr: '' },
  'module-purchase-submodule-additional_purchases-form': { en: '', fr: '' },

  // ── Research Facilities ────────────────────────────────────────────────────
  'module-research-facilities-submodule-research-facilities-form': {
    en: '',
    fr: '',
  },
  'module-research-facilities-submodule-mice_and_fish_animal_facilities-form': {
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
    en: 'The equipment class determines the average power values used to calculate emissions. Update the class in your inventory if it is incorrect.',
    fr: "La classe de l'équipement détermine les valeurs de puissance moyenne utilisées pour le calcul des émissions. Mettez à jour la classe  dans votre inventaire si celle-ci n'est pas appropriée.",
  },
  'module-equipment-submodule-scientific-table-sub_class': {
    en: 'The sub-class allows a more precise determination of the average power values for some equipment classes.',
    fr: "La sous-classe permet une détermination plus précise des valeurs de puissance moyenne pour certaines classes d'équipements.",
  },
  'module-equipment-submodule-scientific-table-active_usage_hours_per_week': {
    en: 'Number of hours per week the equipment is actively in use. Some generic time values have been pre-filled. Please update to make them more specific to your equipment use. Active and standby hours combined cannot exceed 168 h/wk.',
    fr: "Nombre d’heures par semaine pendant lesquelles l’équipement est activement utilisé. Certaines valeurs génériques ont été préremplies. Veuillez les mettre à jour afin qu’elles correspondent plus précisément à l’utilisation de votre équipement. Le total des heures actives et des heures en veille ne peut pas dépasser 168 h/semaine.",
  },
  'module-equipment-submodule-scientific-table-standby_usage_hours_per_week': {
    en: 'Number of hours per week the equipment is in standby use. Some generic time values have been pre-filled. Please update to make them more specific to your equipment use. Active and standby hours combined cannot exceed 168 h/wk.',
    fr: "Nombre d’heures par semaine pendant lesquelles l’équipement est utilisé en mode standby. Certaines valeurs génériques ont été préremplies. Veuillez les mettre à jour afin qu’elles correspondent plus précisément à l’utilisation de votre équipement. Le total des heures actives et des heures en veille ne peut pas dépasser 168 h/semaine.",
  },
  'module-equipment-submodule-scientific-table-active_power_w': {
    en: 'The average active power is indicated by class. It may not fully represent the power of your equipment, in which case please contact us. Please note that we do not want the maximum power value, which can be very different from the average power.',
    fr: "La puissance active moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas merci de nous contacter. Attention, nous ne voulons pas avoir la valeur de puissance maximale qui peut être très différente de la puissance moyenne.",
  },
  'module-equipment-submodule-scientific-table-standby_power_w': {
    en: 'The average standby power is indicated by class. It may not fully represent the power of your equipment, in which case please contact us.',
    fr: "La puissance standby moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas merci de nous contacter.",
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
  'module-research-facilities-submodule-mice_and_fish_animal_facilities-table-researchfacility_name':
    {
      en: '',
      fr: '',
    },
  'module-research-facilities-submodule-mice_and_fish_animal_facilities-table-researchfacility_type':
    {
      en: '',
      fr: '',
    },
  'module-research-facilities-submodule-mice_and_fish_animal_facilities-table-use':
    {
      en: "For EPFL's rodent and fish animal facilities, only the animal housing component is considered. The Phenotyping Unit (UDP) and the Transgenesis Platform (TCF) are not included.",
      fr: "Pour l'utilisation des animaleries rongeurs et poissons à l'EPFL, nous ne considérons que la partie hébergement des animaux et pas ce qui concerne l'unité de phénotypage (UDP) et la plateforme de transgénèse (TCF).",
    },
  'module-research-facilities-submodule-mice_and_fish_animal_facilities-table-kg_co2eq':
    { en: '', fr: '' },

  // ═══════════════════════════════════════════════════════════════════════════
  // MODULE CHART TOOLTIPS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // Each module results section contains a breakdown chart. A (ℹ) icon can
  // appear next to the chart title to give users context about what is
  // included in — or excluded from — the visualisation.

  'module-equipment-charts': {
    en: 'The emissions considered here are those related to the energy required to operate the equipment (scientific, IT, etc.).',
    fr: "Les émissions considérées ici sont celles liées à l'énergie nécessaire à l'utilisation des équipements (scientifiques, informatiques, etc.).",
  },
  'module-buildings-charts': {
    en: 'The emissions considered here are those related to the energy used for heating, lighting, ventilation, and cooling in buildings.',
    fr: "Les émissions considérées ici sont celles liées à l'énergie nécessaire pour le chauffage, l'éclairage, la ventilation et le froid dans les bâtiments.",
  },
  'module-external-cloud-and-ai-charts': {
    en: 'The results are aggregated by service type: external clouds and AI.',
    fr: "Les résultats sont aggrégés par type de service: clouds externes et IA.",
  },
  'module-research-facilities-charts': {
    en: 'If these research activities were performed independently by the unit, the emissions coming from them would be higher. Using shared research facilities helps to reduce overall EPFL emissions.',
    fr: "Si ces activités de recherche étaient menées de manière indépendante par l'unité, les émissions qu'elles génèrent seraient plus élevées. L'utilisation mutualisée d'infrastructures de recherche contribue à réduire les émissions globales de l'EPFL.",
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
    en: 'This corresponds to embedded energy emissions in buildings.',
    fr: "Ces émissions correspondent à l'énergie grise des bâtiments.",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // RESULTS PAGE — CHARTS
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // The results page contains several charts, each with optional (ℹ) icons on
  // their title or on the coloured filter badges above them. These give context
  // about what the chart shows or how a particular filter was calculated.

  'results-charts-it-focus-breakdown-title': {
    en: 'The emissions considered here are those related to the purchase of IT equipment, the energy required for its use, and the use of services (internal or external) such as AI and cloud services.',
    fr: "Les émissions considérées ici sont celles liées à l'achat d'équipement informatique, à l'énergie nécessaire pour l'utiliser, et à l'usage des services (internes ou externes) tels que l'IA et les clouds externes.",
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
    en: 'These emissions are calculated based on research facilities data.',
    fr: 'Ces émissions sont calculées à partir des données propres aux infrastructure de recherche.',
  },
  'results-charts-additional-data-filter': {
    en: "These emissions are calculated based on EPFL's general assumptions.",
    fr: "Ces émissions sont calculées à partir des hypothèses générales de l'EPFL.",
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
    en: 'This section presents two graphs. The first illustrates the reference "net zero" trajectory for EPFL, aligned with the CO₂ emission reduction targets set by the Swiss Confederation and the Climate Act. The second allows you to simulate the evolution of your unit\'s emissions and adjust each category in order to converge towards this reference trajectory.',
    fr: "Cette section présente deux graphiques. Le premier illustre la trajectoire « net zéro » de référence pour l'EPFL, alignée sur les objectifs de réduction des émissions de CO₂ fixés par la Confédération et la Loi Climat. Le second vous permet de simuler l'évolution des émissions de votre unité et d'ajuster chaque catégorie afin de converger vers cette trajectoire de référence.",
  },
  'results-reduction-process_emissions': { en: '', fr: '' },
  'results-reduction-buildings_energy_combustion': { en: '', fr: '' },
  'results-reduction-buildings_room': { en: '', fr: '' },
  'results-reduction-equipment': { en: '', fr: '' },
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

  documentation_editing_rows_tooltips_topic: {
    en: 'Tooltips',
    fr: 'Info-bulles',
  },
  documentation_editing_rows_tooltips_description: {
    en: 'Find all tooltip texts shown as (ℹ) icons throughout the application.',
    fr: "Trouvez tous les textes des info-bulles affichées sous forme d'icônes (ℹ) dans l'application.",
  },
} as const;
