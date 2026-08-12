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
    fr: 'Les émissions provenant du module Bâtiments contribuent aux scopes 1 (combustion d’énergie sur site; par exemple une chaudière à gaz naturel) et scope 2 ( consommation d’électricité pour le chauffage, le refroidissement, la ventilation et l’éclairage).',
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
    fr: "Les émissions du module Voyages professionels contribue au scope 3 de l'empreinte carbone du laboratoire.",
  },
  'module-purchase-title': {
    en: 'The emissions from the Purchases module contribute to Scope 3 of the laboratory’s carbon footprint.',
    fr: "Les émissions du module Achats contribue au scope 3 de l'empreinte carbone du laboratoire.",
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
    en: 'Emissions from research facilities allocated to the units are calculated based on Process emission, Energy combustion, Building, Equipment, and Purchases emissions, using billing or the number of hours used by your unit as the allocation key. If one or several research facilities are missing in the tool, do not hesitate to contact us so that we can provide you with more details.',
    fr: "Les émissions des infrastructures de recherche attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Combustion d'énergie, Bâtiments, Équipements et Achats en considérant comme clé de répartition les facturations ou le nombre d'heures d'utilisation de votre unité. Si une ou plusieurs infrastructures de recherche manquent dans l'outil, n'hésitez pas à nous contacter afin que nous puissions vous fournir plus de détails.",
  },
  'module-research-facilities-submodule-animal_facilities': {
    en: 'Emissions from the rodent and fish facilities are allocated to individual units based on their use of housing units (e.g., cages and aquariums) throughout the year. These emissions are calculated based on the Process emissions, Buildings, Equipment, and Purchases, with the annual number of housing units serving as the allocation key.',
    fr: 'Les émissions des animaleries rongeurs et poissons attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Bâtiments, Équipements et Achats en considérant comme clé de répartition le nombre d’hébergements (cages, aquariums) par année.',
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
    en: 'Enter the total number of FTE of students who worked in your unit over the year',
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
    fr: "Veuillez ajouter les locaux qui manquent dans la liste ci-dessus. Attention, vous devrez répercuter ce changement lors de votre prochaine mise à jour d'Archibus, car celle-ci ne se fait pas automatiquement à travers le Calculateur CO₂.",
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
    fr: 'Chaque étape du trajet doit être saisie comme un déplacement distinct. Par exemple, pour un vol au départ de Genève à destination de Los Angeles avec une escale à Amsterdam : Genève-Amsterdam, Amsterdam-Los-Angeles.',
  },
  'module-professional-travel-submodule-train-form': {
    en: 'Each leg of the trip must be entered as a separate trip. For example, for a train trip from Lausanne to Mannheim: Lausanne–Bern, Bern–Basel, Basel–Mannheim.',
    fr: 'Chaque étape du trajet doit être saisie comme un déplacement distinct. Par exemple, pour un trajet en train  au départ de Lausanne à destination de Mannheim  : Lausanne-Berne, Berne-Bale, Bale-Mannheim.',
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
    fr: "Veuillez ajouter tous les achats liés aux véhicules réglés avec la carte de crédit de l'unité (ex. le carburant, les locations de voiture, les péages, les frais de stationnement ou l'entretien des véhicules.",
  },
  'module-purchase-submodule-other_purchases-form': { en: '', fr: '' },
  'module-purchase-submodule-purchases_centralized-form': { en: '', fr: '' },

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
    en: 'The equipment class determines the average power values used to calculate emissions. Update the class in your inventory if it is incorrect.',
    fr: "La classe de l'équipement détermine les valeurs de puissance moyenne utilisées pour le calcul des émissions. Mettez à jour la classe  dans votre inventaire si celle-ci n'est pas appropriée.",
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
    en: "The emissions shown here are calculated on the basis of the unit's headcount (FTE) and contribute to Scope 3 of the carbon footprint.",
    fr: "Les émissions présentées ici sont calculées sur la base de l'effectif de l'unité (EPT) et contribuent au Scope 3 de l'empreinte carbone.",
  },
  'module-process-emissions-charts': {
    en: 'The emissions considered here are the direct process emissions of the unit, broken down by greenhouse gas. They contribute to Scope 1 of the carbon footprint.',
    fr: "Les émissions considérées ici sont les émissions de procédés directes de l'unité, réparties par gaz à effet de serre. Elles contribuent au Scope 1 de l'empreinte carbone.",
  },
  'module-buildings-charts': {
    en: 'The emissions considered here are those related to the energy used for heating, lighting, ventilation, and cooling in buildings.',
    fr: "Les émissions considérées ici sont celles liées à l'énergie nécessaire pour le chauffage, l'éclairage, la ventilation et le froid dans les bâtiments.",
  },
  'module-equipment-charts': {
    en: 'The emissions considered here are those related to the energy required to operate the equipment (scientific, IT, etc.).',
    fr: "Les émissions considérées ici sont celles liées à l'énergie nécessaire à l'utilisation des équipements (scientifiques, informatiques, etc.).",
  },
  'module-external-cloud-and-ai-charts': {
    en: 'The results are aggregated by service type: external clouds and AI.',
    fr: 'Les résultats sont aggrégés par type de service: clouds externes et IA.',
  },
  'module-professional-travel-charts': {
    en: "The emissions considered here are those related to the unit's professional travel, broken down by mode of transport (plane and train).",
    fr: "Les émissions considérées ici sont celles liées aux voyages professionnels de l'unité, réparties par mode de transport (avion et train).",
  },
  'module-purchase-charts': {
    en: "The emissions considered here are those related to the unit's purchases, broken down by purchase category.",
    fr: "Les émissions considérées ici sont celles liées aux achats de l'unité, réparties par catégorie d'achat.",
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
    en: 'This section presents two graphs. The first allows you to simulate the evolution of your unit emissions and adjust each category in order to converge towards the net zero trajectory. The second illustrates the reference net zero trajectory for EPFL, aligned with the CO₂ emission reduction targets set by the Swiss Confederation and the Climate Act.',
    fr: "Cette section présente deux graphiques. Le premier vous permet de simuler l'évolution des émissions de votre unité et d'ajuster chaque catégorie afin de converger vers la trajectoire net zéro. Le deuxième illustre la trajectoire net zéro de référence pour l'EPFL, alignée sur les objectifs de réduction des émissions de CO₂ fixés par la Confédération et la Loi Climat.",
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

  // ═══════════════════════════════════════════════════════════════════════════
  // CO₂ PROJECT PLANNER — GRANT PROPOSAL SECTION
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // These tooltips appear ONLY inside the "Project Grant" section of a plan.
  // The project-year sections below have their own separate texts, and the
  // Calculator keeps the `module-…` texts further up in this file.

  'planner-grant-section-title': {
    en: 'This section allows you to gather information related to a research project’s carbon footprint as requested by funding agencies. Please contact co2calculator@epfl.ch if the agencies ask for information that you cannot find here.',
    fr: "Cet espace vous permet de collecter les informations liées à l'empreinte carbone d'un projet de recherche demandées par les agences de financement. Merci de contacter co2calculator@epfl.ch si les agences vous demandent des informations que vous ne retrouvez pas ici.",
  },

  'planner-grant-module-headcount-title': {
    en: 'This module automatically displays the main staff categories. Please manually enter the total FTE for a project year. The total number of FTEs is used to generate indicators for additional categories (Scope 3: Food, Commuting, and Waste), as well as the total carbon footprint per FTE for your project within your unit.\n\nThe methodology used is documented on the Documentation pages.',
    fr: "Ce module affiche automatiquement les grandes catégories de personnel. Veuillez ajouter manuellement les EPT total pour une année de projet. Le nombre total d'EPT est utilisé pour générer les indicateurs des catégories additionnelles (Scope 3 : Alimentation, Pendularité et Déchets), ainsi que l'empreinte carbone totale par EPT pour votre projet dans votre unité.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-grant-module-headcount-submodule-member': { en: '', fr: '' },
  'planner-grant-module-headcount-submodule-student': { en: '', fr: '' },

  'planner-grant-module-process-emissions-title': {
    en: 'This module allows you to estimate the carbon footprint of the greenhouse gases generated during your project-specific laboratory activities (e.g., Scope 1 CO₂ emissions from certain laboratory activities, SF₆ emissions when SF₆ is used as a refrigerant).\n\nThe methodology used is documented on the Documentation pages.',
    fr: 'Ce module permet d’estimer l’empreinte carbone des gaz à effet de serre générés lors de vos activités de laboratoire spécifique à votre projet (e.g. émissions de CO₂ Scope 1 dans certaines activités de laboratoire, émissions de SF₆ quand celui-ci est utilisé en tant que fluide frigorigène).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.',
  },
  'planner-grant-module-process-emissions-submodule-process_emissions': {
    en: 'Process Emissions sub-module: Please note that the budget associated with your unit’s process emissions is, in most cases, zero. Indeed, these emissions are either included in your purchases, in which case the corresponding budget should be allocated to the purchases category, or funded by central services, in which case they do not fall within your unit’s scope.',
    fr: 'Sous-module Émissions de procédés : Veuillez noter que le budget associé aux émissions de procédés de votre unité est, dans la plupart des cas, égal à zéro. En effet, ces émissions sont soit incluses dans vos achats, et leur budget doit alors être comptabilisé dans cette catégorie, soit financées par les services centraux, auquel cas elles ne font pas partie du périmètre de votre unité.',
  },

  'planner-grant-module-buildings-title': {
    en: 'This module allows you to estimate the carbon footprint associated with buildings (emissions from energy combustion and indoor sources) (Scope 1 and 2) specific to your project.\n\nThe methodology used is documented in the Documentation section.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux Bâtiments (émissions de combustion d'énergie et locaux) (Scope 1 et 2) spécifique à votre projet.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-grant-module-buildings-submodule-building': {
    en: 'Rooms sub-module: Use the slider to specify the percentage of rooms usage based on the CO₂ calculator’s results in order to estimate their impact within the context of your project (Scope 1). You can also add other rooms used as part of your project.',
    fr: "Sous-module Locaux : À l'aide du curseur, indiquez le pourcentage d'utilisation des locaux spécifique à votre projet par rapport aux résultats du calculateur CO₂ afin d'estimer leur impact (Scope 1). Il est également possible d'ajouter d'autres locaux utilisés dans le cadre de votre projet.",
  },
  'planner-grant-module-buildings-submodule-energy_combustion': {
    en: 'Energy Combustion Emissions sub-module: Use the slider to specify the percentage of energy combustion emissions relative to the CO₂ calculator’s results in order to estimate their impact within the context of your project (Scope 1). You can also add other sources of energy combustion used in your project.',
    fr: "Sous-module Émissions de combustion d'énergie : À l'aide du curseur, indiquez le pourcentage d'émissions liées à la combustion d'énergie spécifique à votre projet par rapport aux résultats du calculateur CO₂ afin d'estimer leur impact (Scope 1). Il est également possible d'ajouter d'autres sources de combustion d'énergie utilisées dans le cadre de votre projet.",
  },

  'planner-grant-module-equipment-title': {
    en: 'This module allows you to estimate the carbon footprint associated with the electricity consumption of equipment (scientific equipment, IT equipment, other equipment) specific to your project (Scope 2).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à la consommation électrique des équipements (Équipements scientifiques, Équipements IT, Autres équipements) spécifique à votre projet (Scope 2).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-grant-module-equipment-submodule-scientific': {
    en: 'Scientific Equipment sub-module: Using the slider, indicate the percentage of electricity consumption attributable to scientific equipment relative to the results of the CO₂ calculator in order to estimate its impact within the scope of your project (Scope 2). It is also possible to add other equipment used as part of your project.',
    fr: "Sous-module Équipements scientifiques : À l'aide du curseur, indiquez le pourcentage de consommation électrique des équipements scientifiques par rapport aux résultats du calculateur CO₂ afin d'estimer leur impact dans le cadre de votre projet (Scope 2). Il est également possible d'ajouter d'autres équipements utilisés dans le cadre de votre projet.",
  },
  'planner-grant-module-equipment-submodule-it': {
    en: 'IT Equipment sub-module: Using the slider, indicate the percentage of electricity consumption attributable to IT equipment relative to the results of the CO₂ calculator in order to estimate its impact within the scope of your project (Scope 2). It is also possible to add other equipment used as part of your project.',
    fr: "Sous-module Équipements informatiques : À l'aide du curseur, indiquez le pourcentage de consommation électrique des équipements informatiques spécifique à votre projet par rapport aux résultats du calculateur CO₂ afin d'estimer leur impact (Scope 2). Il est également possible d'ajouter d'autres équipements utilisés dans le cadre de votre projet.",
  },
  'planner-grant-module-equipment-submodule-other': {
    en: 'Other Equipment sub-module: Using the slider, indicate the percentage of electricity consumption attributable to other equipment relative to the results of the CO₂ calculator in order to estimate its impact within the scope of your project (Scope 2). It is also possible to add other equipment used as part of your project.',
    fr: "Sous-module Autres équipements : À l'aide du curseur, indiquez le pourcentage de consommation électrique des autres équipements spécifique à votre projet par rapport aux résultats du calculateur CO₂ afin d'estimer leur impact (Scope 2). Il est également possible d'ajouter d'autres équipements utilisés dans le cadre de votre projet.",
  },

  'planner-grant-module-external-cloud-and-ai-title': {
    en: 'This module allows you to estimate the carbon footprint associated with external cloud services and external AIs specific to your project (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux services de clouds externes et d'IAs externes spécifique à votre projet (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-grant-module-external-cloud-and-ai-submodule-external_clouds': {
    en: 'External Cloud Services sub-module: Using the slider, indicate the percentage of external cloud service usage relative to the data entered in the CO₂ calculator in order to estimate their impact within the scope of your project for the reference year (Scope 3). It is also possible to add data related to external cloud services.',
    fr: "Sous-module Services de cloud externes : À l'aide du curseur, indiquez le pourcentage d'utilisation des services de cloud externes spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leur impact (Scope 3). Il est également possible d'ajouter des données relatives aux services de cloud externes.",
  },
  'planner-grant-module-external-cloud-and-ai-submodule-external_ai': {
    en: 'External AI Services sub-module: Using the slider, indicate the percentage of external AI service usage relative to the data entered in the CO₂ calculator in order to estimate their impact within the scope of your project for the reference year (Scope 3). It is also possible to add data related to external AI services.',
    fr: "Sous-module Services d'IAs externes : À l'aide du curseur, indiquez le pourcentage d'utilisation des services d'IA externes spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leur impact (Scope 3). Il est également possible d'ajouter des données relatives aux services d'IA externes.",
  },

  'planner-grant-module-professional-travel-title': {
    en: 'This module allows you to estimate the carbon footprint associated with professional travel by plane and/or train specific to your project (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux voyages professionnels effectués en avion et/ou en train spécifique à votre projet (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-grant-module-professional-travel-submodule-plane': {
    en: 'Plane sub-module: Add the flights planned within the scope of your project to estimate their associated impact for the reference year (Scope 3).',
    fr: "Sous-module Avion : À l'aide du curseur, indiquez le pourcentage des voyages professionnels en avion spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leur impact (Scope 3). Il est également possible d'ajouter d'autres vols utilisés dans le cadre de votre projet.",
  },
  'planner-grant-module-professional-travel-submodule-train': {
    en: 'Train sub-module: Add the train journeys planned within the scope of your project to estimate their associated impact for the reference year (Scope 3).',
    fr: "Sous-module Train : À l'aide du curseur, indiquez le pourcentage des voyages professionnels en train spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leur impact (Scope 3). Il est également possible d'ajouter d'autres trajets en train utilisés dans le cadre de votre projet.",
  },

  'planner-grant-module-purchase-title': {
    en: 'This module allows you to estimate the carbon footprint associated with project-specific purchases (Scope 3). To do so, please indicate the budget allocated to the relevant purchasing categories (Scientific Equipment, IT Equipment, Consumables and Accessories, Biological, Chemical and Gas Products, Services, Vehicles, and Other Purchases).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux achats spécifiques à votre projet (Scope 3). Pour cela, veuillez indiquer le budget correspondant aux catégories d'achats (Équipements scientifiques, Équipements informatiques, Consommables et accessoires, Produits biologiques, chimiques et gazeux, Services, Véhicules, Autres achats).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
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
    en: 'This module allows you to estimate the carbon footprint associated with the use of EPFL research infrastructures specific to your project (Scope 3). To do so, add the relevant research infrastructures and animal facilities, indicating the corresponding budget for each.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à l'utilisation des infrastructures de recherche EPFL spécifiques à votre projet (Scope 3). Pour cela, ajoutez les infrastructures de recherche et animaleries en indiquant le budget correspondant.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
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
    en: 'View and complete the estimated carbon impact data by project year here. This data comes from the CO₂ calculator.',
    fr: "Retrouvez et complétez ici les données d'impact carbone estimé par année de projet. Ces données remontent de l'espace calculateur CO₂.",
  },

  'planner-year-module-headcount-title': {
    en: 'This module uses the CO₂ Calculator data for the selected year. Please enter the percentage of staff involved in the project.\n\nThe total number of FTEs (Full-Time Equivalents) is used to calculate indicators for additional categories (Food, Commuting, and Waste) (Scope 3), as well as the total carbon footprint per FTE for your project within your organizational unit.',
    fr: "Ce module considère les données du calculateur CO₂ pour l'année considérée. Veuillez saisir le pourcentage de personnel impliqué dans le projet. Le nombre total d'EPT est utilisé pour générer les indicateurs des catégories additionnelles (Alimentation, Pendularité et Déchets) (Scope 3), ainsi que l'empreinte carbone totale par EPT pour votre projet dans votre unité.",
  },
  'planner-year-module-headcount-submodule-member': { en: '', fr: '' },
  'planner-year-module-headcount-submodule-student': { en: '', fr: '' },

  'planner-year-module-process-emissions-title': {
    en: 'This module allows you to estimate the carbon footprint of greenhouse gas emissions generated by laboratory activities specific to your project (e.g., Scope 1 CO₂ emissions from certain laboratory activities, or SF₆ emissions when used as a refrigerant).\n\nTo do so, please enter the percentage of process emissions attributable to the project based on the data entered in the CO₂ Calculator.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d’estimer l’empreinte carbone des gaz à effet de serre générés lors de vos activités de laboratoire spécifique à votre projet (e.g. émissions de CO₂ Scope 1 dans certaines activités de laboratoire, émissions de SF₆ quand celui-ci est utilisé en tant que fluide frigorigène). Pour cela, veuillez saisir le pourcentage d'émissions de procédés impliqué dans le projet venant des données saisies dans le calculateur CO₂.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-year-module-process-emissions-submodule-process_emissions': {
    en: '',
    fr: '',
  },

  'planner-year-module-buildings-title': {
    en: 'This module allows you to estimate the carbon footprint associated with buildings. This includes emissions from on-site energy combustion in cases where your unit uses a non-centralized energy source (Scope 1), as well as building-related emissions specific to your project (Scope 2), such as heating, cooling, ventilation, and lighting.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux Bâtiments (émissions de combustion d'énergie et locaux) dans le cas où votre unité utilise une source d'énergie non-centralisée (Scope 1) ainsi que celles liées au bâtiment (Scope 2 : chauffage, climatisation, ventilation et éclairage) spécifique à votre projet.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-year-module-buildings-submodule-building': {
    en: 'Rooms sub-module: Using the slider, indicate the percentage of rooms usage attributable to your project relative to the data entered in the CO₂ Calculator in order to estimate its impact (Scope 2).',
    fr: "Sous-module Locaux : À l'aide du curseur, indiquez le pourcentage d'utilisation des locaux spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 1).",
  },
  'planner-year-module-buildings-submodule-energy_combustion': {
    en: 'Energy Combustion Emissions sub-module: Using the slider, indicate the percentage of energy combustion emissions attributable to your project relative to the data entered in the CO₂ Calculator in order to estimate their impact (Scope 1).',
    fr: "Sous-module Émissions de combustion d'énergie : À l'aide du curseur, indiquez le pourcentage d'utilisation d'émissions de combustion spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 1).",
  },

  'planner-year-module-equipment-title': {
    en: 'This module allows you to estimate the carbon footprint associated with the electricity consumption of equipment used specifically for your project (Scientific Equipment, IT Equipment, and Other Equipment) (Scope 2). To do so, please indicate either a usage percentage for each piece of equipment or an overall percentage based on the results obtained from the CO₂ Calculator.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à la consommation électrique des équipements (Équipements scientifiques, Équipements IT, Autres équipements) spécifique à votre projet (Scope 2). Pour cela, veuillez indiquer un pourcentage d'utilisation par équipement spécifique à votre projet ou rentrer un pourcentage global en fonction des résultats obtenus dans le calculateur.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-year-module-equipment-submodule-scientific': {
    en: 'Scientific Equipment sub-module: Using the slider, indicate the percentage of electricity consumption from scientific equipment attributable to your project relative to the data entered in the CO₂ Calculator in order to estimate its impact (Scope 2).',
    fr: "Sous-module Équipements scientifiques : À l'aide du curseur, indiquez le pourcentage de consommation électrique des équipements scientifiques spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 2).",
  },
  'planner-year-module-equipment-submodule-it': {
    en: 'IT Equipment sub-module: Using the slider, indicate the percentage of electricity consumption from IT equipment attributable to your project relative to the data entered in the CO₂ Calculator in order to estimate its impact (Scope 2).',
    fr: "Sous-module Équipements IT : À l'aide du curseur, indiquez le pourcentage de consommation électrique des équipements IT spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 2).",
  },
  'planner-year-module-equipment-submodule-other': {
    en: 'Other Equipment sub-module: Using the slider, indicate the percentage of electricity consumption from other equipment attributable to your project relative to the data entered in the CO₂ Calculator in order to estimate its impact (Scope 2).',
    fr: "Sous-module Autres équipements : À l'aide du curseur, indiquez le pourcentage de consommation électrique des autres équipements spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 2).",
  },

  'planner-year-module-external-cloud-and-ai-title': {
    en: 'This module allows you to estimate the carbon footprint associated with external cloud services and external AI services used specifically for your project (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux services de clouds externes et d'IAs externes spécifique à votre projet (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-year-module-external-cloud-and-ai-submodule-external_clouds': {
    en: 'External Cloud Services sub-module: Use the slider to indicate the share of external cloud service usage attributable to your project relative to the data entered in the CO₂ Calculator. This information is used to estimate the project’s impact (Scope 3).',
    fr: "Sous-module Services de clouds externes : À l'aide du curseur, indiquez le pourcentage d'utilisation de services de clouds externes spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 3).",
  },
  'planner-year-module-external-cloud-and-ai-submodule-external_ai': {
    en: 'External AI Services sub-module: Use the slider to indicate the share of external AI service usage attributable to your project relative to the data entered in the CO₂ Calculator. This information is used to estimate the project’s impact (Scope 3).',
    fr: "Sous-module Services d'IAs externes : À l'aide du curseur, indiquez le pourcentage d'utilisation de services d'IAs externes spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 3).",
  },

  'planner-year-module-professional-travel-title': {
    en: 'This module allows you to estimate the carbon footprint associated with professional travel (plane and/or train) specific to your project (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux voyages professionnels (en avion et/ou en train) spécifique à votre projet (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-year-module-professional-travel-submodule-plane': {
    en: 'Plane sub-module: Use the slider to indicate the share of professional plane travel attributable to your project relative to the data entered in the CO₂ Calculator. This information is used to estimate the project’s impact (Scope 3).',
    fr: "Sous-module Avion : À l'aide du curseur, indiquez le pourcentage de voyages professionnels en avion spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 3).",
  },
  'planner-year-module-professional-travel-submodule-train': {
    en: 'Train sub-module: Use the slider to indicate the share of professional train travel attributable to your project relative to the data entered in the CO₂ Calculator. This information is used to estimate the project’s impact (Scope 3).',
    fr: "Sous-module Train : À l'aide du curseur, indiquez le pourcentage de voyages professionnels en train spécifique à votre projet par rapport aux données saisies dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 3).",
  },

  'planner-year-module-purchase-title': {
    en: 'This module allows you to estimate the carbon footprint associated with project-specific purchases (Scope 3). To do so, please indicate the budget allocated to the relevant purchasing categories (Scientific Equipment, IT Equipment, Consumables and Accessories, Biological, Chemical and Gas Products, Services, Vehicles, and Other Purchases).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée aux achats spécifiques à votre projet (Scope 3). Pour cela, veuillez indiquer le budget correspondant aux catégories d'achats (Équipements scientifiques, Équipements informatiques, Consommables et accessoires, Produits biologiques, chimiques et gazeux, Services, Véhicules, Autres achats).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
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
    en: 'This module allows you to estimate the carbon footprint associated with the use of EPFL research facilities specific to your project (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'estimer l'empreinte carbone liée à l'utilisation des infrastructures de recherche EPFL spécifiques à votre projet (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'planner-year-module-research-facilities-submodule-research-facilities': {
    en: 'Research facilities sub-module: Use the slider to indicate the share of usage for each research facility attributable to your project relative to the data obtained from the CO₂ Calculator. This information is used to estimate the project’s impact (Scope 3).',
    fr: "Sous-module Infrastructures de recherche : À l'aide du curseur, indiquez le pourcentage d'utilisation par infrastructure de recherche spécifique à votre projet par rapport aux données obtenues dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 3).",
  },
  'planner-year-module-research-facilities-submodule-animal_facilities': {
    en: 'Rodent and fish animal facilities sub-module: Use the slider to indicate the share of rodent and fish animal facilities usage attributable to your project relative to the data obtained from the CO₂ Calculator. This information is used to estimate the project’s impact (Scope 3).',
    fr: "Sous-module Animaleries : À l'aide du curseur, indiquez le pourcentage d'utilisation des animaleries spécifique à votre projet par rapport aux données obtenues dans le calculateur CO₂ afin d'estimer leurs impacts (Scope 3).",
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CO₂ EXPLORER
  // ═══════════════════════════════════════════════════════════════════════════
  //
  // These tooltips appear only on the CO₂ Explorer page, next to each module
  // and sub-module title.

  'explorer-module-headcount-title': {
    en: 'This module uses staff data to generate indicators for additional categories (Food, Commuting, and Waste) (Scope 3), as well as the estimated total carbon footprint per FTE for your module.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module considère les données du personnel afin de générer les indicateurs des catégories additionnelles (Alimentation, Pendularité et Déchets) (Scope 3), ainsi que l'empreinte carbone totale par EPT pour votre module estimé.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
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
    en: 'This module allows you to explore the carbon footprint of greenhouse gas emissions generated by laboratory activities specific to your project (e.g., Scope 1 CO₂ emissions from certain laboratory activities and SF₆ emissions when used as a refrigerant).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l’empreinte carbone des gaz à effet de serre générés lors de vos activités de laboratoire spécifique à votre projet (e.g. émissions de CO₂ Scope 1 dans certaines activités de laboratoire, émissions de SF₆ quand celui-ci est utilisé en tant que fluide frigorigène).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
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
    en: 'Rooms sub-module: Explore the carbon footprint associated with the use of rooms.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Locaux : Explorez l'empreinte carbone liée à l'utilisation de certains locaux.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-buildings-submodule-energy_combustion': {
    en: 'Energy Combustion Emissions sub-module: Explore the carbon footprint associated with energy combustion emissions.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Émissions de combustion d'énergie : Explorez l'empreinte carbone liée aux émissions de combustion d'énergie.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },

  'explorer-module-equipment-title': {
    en: 'This module allows you to explore the carbon footprint associated with the electricity consumption of equipment (Scientific Equipment, IT Equipment, and Other Equipment) (Scope 2).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée à la consommation électrique des équipements (Équipements scientifiques, Équipements IT, Autres équipements) (Scope 2).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-equipment-submodule-scientific': {
    en: 'Scientific Equipment sub-module: Explore the carbon footprint of a scientific equipment item.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Équipements scientifiques : Explorez l'empreinte carbone d'un équipement scientifique.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-equipment-submodule-it': {
    en: 'IT Equipment sub-module: Explore the carbon footprint of an IT equipment item.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Équipements IT : Explorez l'empreinte carbone d'un équipement IT.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-equipment-submodule-other': {
    en: 'Other Equipment sub-module: Explore the carbon footprint of another type of equipment.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Autres équipements : Explorez l'empreinte carbone d'un autre type d'équipement.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },

  'explorer-module-external-cloud-and-ai-title': {
    en: 'This module allows you to explore the carbon footprint associated with the use of external cloud services and external AI services (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée à l'utilisation des services de clouds externes et d'IAs externes (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-external-cloud-and-ai-submodule-external_clouds': {
    en: 'External Cloud Services sub-module: Explore the carbon footprint of an external cloud service.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Services de clouds externes : Explorez l'empreinte carbone d'un service de clouds externes.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-external-cloud-and-ai-submodule-external_ai': {
    en: 'External AI Services sub-module: Explore the carbon footprint of an external AI service.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Services d'IAs externes : Explorez l'empreinte carbone d'un service d'IAs externes.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },

  'explorer-module-professional-travel-title': {
    en: 'This module allows you to explore the carbon footprint associated with professional travel (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée aux voyages professionnels (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-professional-travel-submodule-plane': {
    en: 'Plane sub-module: Explore the carbon footprint of a professional flight.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Avion : Explorez l'empreinte carbone d'un voyage professionnel en avion.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-professional-travel-submodule-train': {
    en: 'Train sub-module: Explore the carbon footprint of a professional train journey.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Train : Explorez l'empreinte carbone d'un voyage professionnel en train.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },

  'explorer-module-purchase-title': {
    en: 'This module allows you to explore the carbon footprint associated with purchases across the following categories: Scientific Equipment, IT Equipment, Consumables and Accessories, Biological, Chemical and Gas Products, Services, Vehicles, Other Purchases, and Centralized Purchases (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée aux achats selon les catégories suivantes : Équipements scientifiques, Équipements informatiques, Consommables et accessoires, Produits biologiques, chimiques et gazeux, Services, Véhicules, Autres achats et Achats centralisés (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-scientific_equipment': {
    en: 'Scientific Equipment sub-module: Explore the carbon footprint associated with the purchase of scientific equipment according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Équipements scientifiques : Explorez l'empreinte carbone de l'achat d'un équipement scientifique selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-it_equipment': {
    en: 'IT Equipment sub-module: Explore the carbon footprint associated with the purchase of IT equipment according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Équipements informatiques : Explorez l'empreinte carbone de l'achat d'un équipement informatique selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-consumable_accessories': {
    en: 'Consumables and Accessories sub-module: Explore the carbon footprint associated with the purchase of consumables and accessories according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Consommables et accessoires : Explorez l'empreinte carbone de l'achat d'un consommable et accessoire selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-biological_chemical_gaseous_product': {
    en: 'Biological, Chemical and Gas Products sub-module: Explore the carbon footprint associated with the purchase of biological, chemical, and gas products according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Produits biologiques, chimiques et gazeux : Explorez l'empreinte carbone de l'achat d'un produit biologique, chimique et gazeux selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-services': {
    en: 'Services sub-module: Explore the carbon footprint associated with the purchase of a service according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Services : Explorez l'empreinte carbone de l'achat d'un service selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-vehicles': {
    en: 'Vehicles sub-module: Explore the carbon footprint associated with the purchase of a vehicle according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Véhicules : Explorez l'empreinte carbone de l'achat d'un véhicule selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-other_purchases': {
    en: 'Other Purchases sub-module: Explore the carbon footprint associated with other purchases according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Autres achats : Explorez l'empreinte carbone d'un achat de type autre selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-purchase-submodule-purchases_centralized': {
    en: 'Centralized Purchases sub-module: Explore the carbon footprint associated with a centralized purchase according to the UNSPSC classification.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Achats centralisés : Explorez l'empreinte carbone d'un achat centralisé selon la classification UNSPSC.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },

  'explorer-module-research-facilities-title': {
    en: 'This module allows you to explore the carbon footprint associated with the use of EPFL research facilities (Scope 3).\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Ce module permet d'explorer l'empreinte carbone liée à l'utilisation des infrastructures de recherche EPFL (Scope 3).\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-research-facilities-submodule-research-facilities': {
    en: 'Research Facilities sub-module: Explore the carbon footprint associated with the use of a research facility. Please enter the corresponding budget and/or number of usage hours depending on the facility.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Infrastructures de recherche : Explorez l'empreinte carbone liée à l'utilisation d'une infrastructure de recherche. Veuillez rentrer un budget et/ou des heures d'utilisation selon l'infrastructure.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
  },
  'explorer-module-research-facilities-submodule-animal_facilities': {
    en: 'Animal Facilities sub-module: Explore the carbon footprint associated with the use of an animal facility. Please enter the number of housing units for rodents and fish.\n\nThe methodology used is documented in the Documentation pages.',
    fr: "Sous-module Animaleries : Explorez l'empreinte carbone liée à l'utilisation d'une animalerie. Veuillez rentrer un nombre d'hébergements pour les rongeurs et poissons.\n\nLa méthodologie utilisée est documentée dans les pages Documentation.",
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
