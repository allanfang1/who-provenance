from postgres import *
import yaml

with open("benchmark/config.yaml", "r") as f:
    config = yaml.safe_load(f)

for experiment in config["experiments"]:
    print(f"Running {experiment['name']}")
    for run in range(1, experiment["iterations"] + 1):
        print(f"Iteration {run}")
        reset_database(experiment["database"])
        create_schema(experiment["database"])
        create_staging_schema(experiment["database"])
        load_data(experiment["database"], scale=experiment["scale"])
        install_provenance(experiment["provenance"])
        for update in range(1, experiment["updates"] + 1):
            run_benchmark(experiment["database"], experiment["name"],
                          run, scale=experiment["scale"], update=update)
