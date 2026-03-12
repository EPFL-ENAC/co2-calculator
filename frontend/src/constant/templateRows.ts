//done
export const csvHeadcountContent =
  'name,position_title,position_category,user_institutional_id,fte,note';
export const csvProcessesContent = 'category,subcategory,quantity,note';
export const csvBuildingsContent = `building_location,building_name,room_name,room_type,note`;
export const csvBuildingsCombustionContent = 'name,unit,quantity,note';
export const csvEquipmentContent =
  'name,equipment_class,sub_class,active_usage_hours_per_week,standby_usage_hours_per_week,note';
export const csvPurchaseContent =
  'name,supplier,quantity,total_spent_amount,currency,purchase_institutional_code,purchase_institutional_description,purchase_additional_code,note';
export const csvExternalCloudContent =
  'service_type,provider,spent_amount,currency,note';
export const csvExternalAIContent =
  'provider,usage_type,requests_per_user_per_day,user_count,note';

export const csvDefaultContent = 'not_implemented_yet';

export const csvProfessionalTravelPlaneContent =
  'origin_iata,destination_iata,user_institutional_id,departure_date,number_of_trips,cabin_class,note';

export const csvProfessionalTravelTrainContent =
  'origin_name,destination_name,user_institutional_id,departure_date,number_of_trips,cabin_class,note';
