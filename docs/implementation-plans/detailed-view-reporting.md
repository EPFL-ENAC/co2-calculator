CREATE TABLE emission_type_mapping (
id INT PRIMARY KEY,
name TEXT NOT NULL
);

INSERT INTO emission_type_mapping (id, name) VALUES
-- food
(10000, 'food'),
(10001, 'food**vegetarian'),
(10002, 'food**non_vegetarian'),

-- waste
(20000, 'waste'),
(20001, 'waste**incineration'),
(20002, 'waste**composting'),
(20003, 'waste**biogas'),
(2000301, 'waste**biogas**organic_waste_food_leftovers'),
(2000302, 'waste**biogas**cooking_vegetable_oil'),
(20004, 'waste**recycling'),
(2000401, 'waste**recycling**paper'),
(2000402, 'waste**recycling**cardboard'),
(2000403, 'waste**recycling**plastics'),
(2000404, 'waste**recycling**glass'),
(2000405, 'waste**recycling**ferrous_metals'),
(2000406, 'waste**recycling**non_ferrous_metals'),
(2000407, 'waste**recycling**electronics'),
(2000408, 'waste**recycling**wood'),
(2000409, 'waste**recycling**pet'),
(2000410, 'waste**recycling**aluminum'),
(2000411, 'waste**recycling**textile'),
(2000412, 'waste**recycling**toner_and_ink_cartridges'),
(2000413, 'waste**recycling**inert_waste'),

-- commuting
(30000, 'commuting'),
(30001, 'commuting**walking'),
(30002, 'commuting**cycling'),
(30003, 'commuting**powered_two_wheeler'),
(30004, 'commuting**public_transport'),
(30005, 'commuting\_\_car'),

-- professional travel
(50000, 'professional_travel'),
(50100, 'professional_travel**train'),
(50101, 'professional_travel**train**class_1'),
(50102, 'professional_travel**train**class_2'),
(50200, 'professional_travel**plane'),
(50201, 'professional_travel**plane**first'),
(50202, 'professional_travel**plane**business'),
(50203, 'professional_travel**plane**eco'),

-- buildings
(60000, 'buildings'),
(60100, 'buildings\_\_rooms'),

(60101, 'buildings**rooms**lighting'),
(6010101, 'buildings**rooms**lighting**office'),
(6010102, 'buildings**rooms**lighting**laboratories'),
(6010103, 'buildings**rooms**lighting**archives'),
(6010104, 'buildings**rooms**lighting**libraries'),
(6010105, 'buildings**rooms**lighting**auditoriums'),
(6010106, 'buildings**rooms**lighting**miscellaneous'),

(60102, 'buildings**rooms**cooling'),
(6010201, 'buildings**rooms**cooling**office'),
(6010202, 'buildings**rooms**cooling**laboratories'),
(6010203, 'buildings**rooms**cooling**archives'),
(6010204, 'buildings**rooms**cooling**libraries'),
(6010205, 'buildings**rooms**cooling**auditoriums'),
(6010206, 'buildings**rooms**cooling**miscellaneous'),

(60103, 'buildings**rooms**ventilation'),
(6010301, 'buildings**rooms**ventilation**office'),
(6010302, 'buildings**rooms**ventilation**laboratories'),
(6010303, 'buildings**rooms**ventilation**archives'),
(6010304, 'buildings**rooms**ventilation**libraries'),
(6010305, 'buildings**rooms**ventilation**auditoriums'),
(6010306, 'buildings**rooms**ventilation**miscellaneous'),

(60104, 'buildings**rooms**heating_elec'),
(6010401, 'buildings**rooms**heating_elec**office'),
(6010402, 'buildings**rooms**heating_elec**laboratories'),
(6010403, 'buildings**rooms**heating_elec**archives'),
(6010404, 'buildings**rooms**heating_elec**libraries'),
(6010405, 'buildings**rooms**heating_elec**auditoriums'),
(6010406, 'buildings**rooms**heating_elec**miscellaneous'),

(60105, 'buildings**rooms**heating_thermal'),
(6010501, 'buildings**rooms**heating_thermal**office'),
(6010502, 'buildings**rooms**heating_thermal**laboratories'),
(6010503, 'buildings**rooms**heating_thermal**archives'),
(6010504, 'buildings**rooms**heating_thermal**libraries'),
(6010505, 'buildings**rooms**heating_thermal**auditoriums'),
(6010506, 'buildings**rooms**heating_thermal**miscellaneous'),

(60200, 'buildings**combustion'),
(60201, 'buildings**combustion**natural_gas'),
(60202, 'buildings**combustion**heating_oil'),
(60203, 'buildings**combustion**biomethane'),
(60204, 'buildings**combustion**pellets'),
(60205, 'buildings**combustion**forest_chips'),
(60206, 'buildings**combustion**wood_logs'),
(60300, 'buildings**embodied_energy'),

-- process emissions
(70000, 'process_emissions'),
(70100, 'process_emissions**ch4'),
(70200, 'process_emissions**co2'),
(70300, 'process_emissions**n2o'),
(70400, 'process_emissions**refrigerants'),

-- equipment
(80000, 'equipment'),
(80100, 'equipment**scientific'),
(80200, 'equipment**it'),
(80300, 'equipment\_\_other'),

-- purchases
(90000, 'purchases'),
(90100, 'purchases**goods_and_services'),
(90200, 'purchases**scientific_equipment'),
(90300, 'purchases**it_equipment'),
(90400, 'purchases**consumable_accessories'),
(90500, 'purchases**biological_chemical_gaseous'),
(90600, 'purchases**services'),
(90700, 'purchases**vehicles'),
(90800, 'purchases**other'),
(90900, 'purchases**additional'),
(90901, 'purchases**additional\_\_ln2'),

-- research facilities
(100000, 'research_facilities'),
(100100, 'research_facilities**facilities'),
(100200, 'research_facilities**animal'),

-- external
(110000, 'external'),
(110100, 'external**clouds'),
(110101, 'external**clouds**virtualisation'),
(110102, 'external**clouds**calcul'),
(110103, 'external**clouds**stockage'),
(110200, 'external**ai'),
(110201, 'external**ai**provider_google'),
(110202, 'external**ai**provider_mistral_ai'),
(110203, 'external**ai**provider_anthropic'),
(110204, 'external**ai**provider_openai'),
(110205, 'external**ai**provider_cohere'),
(110206, 'external**ai**provider_others');

pivot that generate the sql

WITH keys AS (
SELECT DISTINCT
(jsonb_object_keys(cr.stats::jsonb -> 'by_emission_type'))::int AS id
FROM carbon_reports cr
),
cols AS (
SELECT
k.id,
m.name
FROM keys k
LEFT JOIN emission_type_mapping m ON m.id = k.id
)
SELECT
'SELECT
cr.year,
u.institutional_id,

        (cr.stats->>''scope1'')::float AS scope1,
        (cr.stats->>''scope2'')::float AS scope2,
        (cr.stats->>''scope3'')::float AS scope3,
        (cr.stats->>''total'')::float AS total,' ||

    string_agg(
        format(
            'COALESCE((cr.stats->''by_emission_type''->>''%s'')::float, 0) AS "%s"',
            id,
            COALESCE(name, id::text)
        ),
        ',\n        '
        ORDER BY id
    ) ||

    '

    FROM carbon_reports cr
    JOIN units u ON u.id = cr.unit_id

    ORDER BY cr.year, u.institutional_id;
    '

FROM cols;

-->
here it is

SELECT
cr.year,
u.institutional_id,

        (cr.stats->>'scope1')::float AS scope1,
        (cr.stats->>'scope2')::float AS scope2,
        (cr.stats->>'scope3')::float AS scope3,
        (cr.stats->>'total')::float AS total,COALESCE((cr.stats->'by_emission_type'->>'10000')::float, 0) AS "food",
    	COALESCE((cr.stats->'by_emission_type'->>'20000')::float, 0) AS "waste",
    	COALESCE((cr.stats->'by_emission_type'->>'30000')::float, 0) AS "commuting"

    FROM carbon_reports cr
    JOIN units u ON u.id = cr.unit_id

    ORDER BY cr.year, u.institutional_id;
