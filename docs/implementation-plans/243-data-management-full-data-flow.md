todo-for-dataentry

1. replace factors on upload (basic)
2. replace data on upload (basic)
3. kg_co2eq from csv should overide emission
4. change the frontend to match Charlie's behavior
5. display status! from the database backend
6. display full log! and more status info!?
   git d

let's analyze the flow in base_csv_provider to understand what's going on with the base_csv_provider

we should rewrite it so it matches better the POST/create function in the carbon_report_module

(we could always abstract that in another layer if you think that's a good idea, but don't overdoit)
