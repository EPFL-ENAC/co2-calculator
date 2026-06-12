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
    en: 'The total FTE is used to generate the generic indicators for Food and Commuting, as well as total carbon footprint per FTE for your unit.',
    fr: "Le nombre total d'EPT est utilisé pour générer les indicateurs génériques relatifs à l'Alimentation et au Mobilité pendulaire, ainsi que l'empreinte carbone totale par EPT pour votre unité.",
  },
  'module-process-emissions-title': {
    en: 'The amount of each greenhouse gas emitted should be estimated before entering the value in the calculator (e.g. taking into account that only X% of the SF₆ used is ultimately emitted)',
    fr: 'La quantité de chaque gaz à effet de serre émise doit être estimée avant de saisir la valeur dans le calculateur (par ex. en prenant en compte que seulement X % du SF₆ utilisé est finalement émis)',
  },
  'module-buildings-title': { en: '', fr: '' },
  'module-equipment-title': {
    en: "The emissions from the equipment module contribute to Scope 2 of the laboratory's carbon footprint.",
    fr: "Les émissions du module équipement contribue au Scope 2 de l'empreinte carbone du laboratoire.",
  },
  'module-external-cloud-and-ai-title': {
    en: 'You can add data one at a time using the Add button below, or upload several entries at once using a file that follows the template.',
    fr: 'Vous pouvez ajouter les données une par une en utilisant le bouton « Ajouter » ci-dessous, ou importer plusieurs entrées à la fois via un fichier respectant le modèle fourni.',
  },
  'module-professional-travel-title': { en: '', fr: '' },
  'module-purchase-title': { en: '', fr: '' },
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
    en: 'You can add data one at a time using the Add FTE below, or upload several entries at once using a file that follows the template.',
    fr: 'Vous pouvez ajouter les données une par une en utilisant le bouton « Ajouter un EPT » ci-dessous, ou importer plusieurs entrées à la fois via un fichier respectant le modèle fourni.',
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
  'module-professional-travel-submodule-plane': { en: '', fr: '' },
  'module-professional-travel-submodule-train': { en: '', fr: '' },

  // ── Purchases ──────────────────────────────────────────────────────────────
  'module-purchase-submodule-scientific_equipment': {
    en: 'For this category, EPFL-specific emission factors are used.',
    fr: "Pour cette catégorie, les facteurs d'émission spécifiques à l'EPFL sont utilisés.",
  },
  'module-purchase-submodule-it_equipment': { en: '', fr: '' },
  'module-purchase-submodule-consumable_accessories': { en: '', fr: '' },
  'module-purchase-submodule-biological_chemical_gaseous_product': {
    en: '',
    fr: '',
  },
  'module-purchase-submodule-services': { en: '', fr: '' },
  'module-purchase-submodule-vehicles': { en: '', fr: '' },
  'module-purchase-submodule-other_purchases': { en: '', fr: '' },
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
    en: 'The emissions from the mice and fish facilities are allocated to the units and calculated based on Process emission, Energy combustion, Building, Equipment, and Purchases emissions, using the number of housing units (cages, aquariums) per year as the allocation key.',
    fr: "Les émissions des animaleries rongeurs et poissons sont attribuées aux unités sont calculées sur la base des émissions des Émissions de procédés, Combustion d'énergie, Bâtiments, Équipements et Achats en considérant comme clé de répartition le nombre d'hébergements (cages, aquariums) par année.",
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
    en: "Due to data-protection rules, students' names and individual FTE are not shown automatically.",
    fr: 'En raison des règles de protection des données, les noms des étudiant·es et les EPT individuels ne sont pas affichés automatiquement.',
  },

  // ── Process Emissions ──────────────────────────────────────────────────────
  'module-process-emissions-submodule-process_emissions-form': {
    en: '',
    fr: '',
  },

  // ── Buildings ──────────────────────────────────────────────────────────────
  'module-buildings-submodule-building-form': { en: '', fr: '' },
  'module-buildings-submodule-energy_combustion-form': {
    en: 'Enter the sources of fossil or non-fossil energy combustion if they are not taken into account in the main module.',
    fr: "Entrez les sources de combustion d'énergie fossiles ou non-fossiles si celles-ci ne sont pas prises en compte dans le module principal.",
  },

  // ── Equipment ──────────────────────────────────────────────────────────────
  'module-equipment-submodule-scientific-form': {
    en: 'Add a scientific equipment item that is not already in your inventory. Remember to also add it to your official inventory so it is included in future years.',
    fr: "Ajoutez un équipement scientifique qui ne figure pas encore dans votre inventaire. Pensez également à l'ajouter à votre inventaire officiel afin qu'il soit inclus dans les années futures.",
  },
  'module-equipment-submodule-it-form': {
    en: 'Add an IT equipment item that is not already in your inventory. Remember to also add it to your official inventory so it is included in future years.',
    fr: "Ajoutez un équipement informatique qui ne figure pas encore dans votre inventaire. Pensez également à l'ajouter à votre inventaire officiel afin qu'il soit inclus dans les années futures.",
  },
  'module-equipment-submodule-other-form': {
    en: 'Add another equipment item that is not already in your inventory. Remember to also add it to your official inventory so it is included in future years.',
    fr: "Ajoutez un autre équipement qui ne figure pas encore dans votre inventaire. Pensez également à l'ajouter à votre inventaire officiel afin qu'il soit inclus dans les années futures.",
  },

  // ── External Cloud & AI ────────────────────────────────────────────────────
  'module-external-cloud-and-ai-submodule-external_clouds-form': {
    en: '',
    fr: '',
  },
  'module-external-cloud-and-ai-submodule-external_ai-form': { en: '', fr: '' },

  // ── Professional Travel ────────────────────────────────────────────────────
  'module-professional-travel-submodule-plane-form': {
    en: 'Please enter the details of your trip by train of flight in Switzerland or abroad. Every leg of the journey needs to be entered a new trip (e.g. Lausanne to New York would be 1. a train from Lausanne to Geneva Airport, then 2. a flight from Geneva Airport to Paris-Charles de Gaulle and 3. A flight from Paris-Charles de Gaulle to John F. Kennedy International Airport). The return can be selected by checking the box provided for this purpose.',
    fr: "Veuillez saisir les détails de votre voyage en train ou en avion, en Suisse ou à l'étranger. Chaque étape du trajet doit être saisie comme un nouveau voyage (par ex. : Lausanne–New York correspondrait à 1. un trajet en train de Lausanne à l'aéroport de Genève, puis 2. un vol de l'aéroport de Genève à Paris–Charles-de-Gaulle et 3. un vol de Paris–Charles-de-Gaulle à l'aéroport international John-F.-Kennedy). Le retour peut être sélectionné en cochant la case prévue à cet effet.",
  },
  'module-professional-travel-submodule-train-form': {
    en: 'Please enter the details of your trip by train of flight in Switzerland or abroad. Every leg of the journey needs to be entered a new trip (e.g. Lausanne to New York would be 1. a train from Lausanne to Geneva Airport, then 2. a flight from Geneva Airport to Paris-Charles de Gaulle and 3. A flight from Paris-Charles de Gaulle to John F. Kennedy International Airport). The return can be selected by checking the box provided for this purpose.',
    fr: "Veuillez saisir les détails de votre voyage en train ou en avion, en Suisse ou à l'étranger. Chaque étape du trajet doit être saisie comme un nouveau voyage (par ex. : Lausanne–New York correspondrait à 1. un trajet en train de Lausanne à l'aéroport de Genève, puis 2. un vol de l'aéroport de Genève à Paris–Charles-de-Gaulle et 3. un vol de Paris–Charles-de-Gaulle à l'aéroport international John-F.-Kennedy). Le retour peut être sélectionné en cochant la case prévue à cet effet.",
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
  'module-purchase-submodule-vehicles-form': { en: '', fr: '' },
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
    en: 'The equipment class determines the average power values used for the emission calculation. Update the class if the one from your inventory is not appropriate.',
    fr: "La classe de l'équipement détermine les valeurs de puissance moyenne utilisées pour le calcul des émissions. Mettez à jour la classe si celle issue de votre inventaire n'est pas appropriée.",
  },
  'module-equipment-submodule-scientific-table-sub_class': {
    en: 'The sub-class allows a more precise determination of the average power values for some equipment classes.',
    fr: "La sous-classe permet une détermination plus précise des valeurs de puissance moyenne pour certaines classes d'équipements.",
  },
  'module-equipment-submodule-scientific-table-active_usage_hours_per_week': {
    en: 'Number of hours per week the equipment is actively in use. It is recommended to make a conservative (not underestimated) estimate.',
    fr: "Nombre d'heures par semaine pendant lesquelles l'équipement est activement utilisé. Il est recommandé de faire une estimation conservatrice (non sous-estimée).",
  },
  'module-equipment-submodule-scientific-table-standby_usage_hours_per_week': {
    en: 'Number of hours per week the equipment is on standby (powered on but not actively used). Active and standby hours combined cannot exceed 168 h/wk.',
    fr: "Nombre d'heures par semaine pendant lesquelles l'équipement est en veille (allumé mais non activement utilisé). Les heures actives et standby combinées ne peuvent pas dépasser 168 h/semaine.",
  },
  'module-equipment-submodule-scientific-table-active_power_w': {
    en: 'The average power is indicated by class. It may not fully represent the power of your equipment, in which case please contact us. Please note that we do not want the maximum power value, which can be very different from the average power.',
    fr: "La puissance moyenne est indiquée par classe. il est possible qu'elle ne soit pas totalement représentative de celle de votre équipement, auquel cas merci de nous contacter. Attention, nous ne voulons pas avoir la valeur de puissance maximale qui peut être très différente de la puissance moyenne.",
  },
  'module-equipment-submodule-scientific-table-standby_power_w': {
    en: '',
    fr: '',
  },
  'module-equipment-submodule-scientific-table-kg_co2eq': {
    en: 'The uncertainty of these values may be high and depends on the representativeness of the power, the hours of use, and the use parameters.',
    fr: "L'incertitude de ces valeurs peut être haute et dépend de la représentativité de la puissance, des heures d'utilisation et des paramètre d'utilisation.",
  },
  'module-equipment-submodule-scientific-table-t_co2eq': {
    en: 'The uncertainty of these values may be high and depends on the representativeness of the power, the hours of use, and the use parameters.',
    fr: "L'incertitude de ces valeurs peut être haute et dépend de la représentativité de la puissance, des heures d'utilisation et des paramètre d'utilisation.",
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
      en: 'For the mice and fish facilities of the CPG unit, we consider only the annual housing component, and not phenotyping or UDP.',
      fr: "Pour les animaleries rongeurs et poissons de l'unité CPG, nous ne considérons que la partie hébergement annuel et non le phénotypage ou UDP.",
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
    en: 'Here, we visualize the emissions corresponding to the use of AI and external clouds. Other emissions related to IT services are present in other modules, such as IT equipment purchases in the Purchases module, electricity consumption in the Equipment module, and the use of internal clouds in the Research Facilities module.',
    fr: "Ici, on visualise les émissions correspondantes à l'utilisation de l'IA et de clouds externes. D'autres émissions liées aux services informatiques sont présentes dans d'autres modules, comme les achats d'équipements informatiques dans le module Achats, la consommation d'électricité dans le module Équipement et l'utilisation de clouds internes dans le module Infrastructure de recherche.",
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
    en: 'A km driven by car is equivalent to {value}kg CO₂-eq',
    fr: 'Un km parcouru en voiture est équivalent à {value}kg CO₂-eq',
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
