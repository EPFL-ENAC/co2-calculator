1 - use the schemas/factor.py to upload factors on the data-management page
2 - refactor the schemas/factor.py inside modules so that it's consistent to data-entries
3 - in base_csv_provider: rewrite totally the \_resolve_carbon_report_modules logic
we curently dynamically insert missing units line 467 - 480/ we should sync all units like
in the seed/seed_units_from_accred.py
4 - fix the travel-api sync now that we have a carbon_report_module logic like in base_csv_provider
4 - SUPER IMPORTANT THING: when uploading data: we should 'REPLACE' the previously uploaded data, and don't touch to
manually inserted data_entry -> to do that: we should have a 'created_by' field/ maybe updated_at field on every data_entry
-> if created_by = ':job_id' created_by_entity = 'csv_upload' ? for instance, then we delete + replace

Here is the flow of what the data update should look like:

-> upsert data_entries -> update corresponding emissions -> end

Here is the flow of what the factor update should look like
a) one emission_type -> 1_N factors
b) for every emission_type we have strategy A and B to retrieve corresponding factors,
--> strategy A use primarty_factor_id, strategy B use data_entry to infer factor_ids

1.  -> retrieve ALL factors.id of the corresponding emission_types of the data_entry_type of uload factors
2.  -> find all corresponding data_entry
3.  -> DUMP all the old factors
4.  -> upload new factors
5.  -> for every data_entry --> if STRAT A --> we need to update the primary_factor_id else Nothing
6.  -> once primary_factor_id updated, recompute and update all data_entry_emissions
