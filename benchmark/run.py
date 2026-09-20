from postgres import *
import yaml

def run_experiment():
    with open("benchmark/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    for experiment in config["experiments"]:
        print(f"Running {experiment['name']}")
        for run in range(1, experiment["iterations"] + 1):
            db_name = experiment["database"]
            print(f"Iteration {run}")
            reset_database(db_name)
            create_schema(db_name, experiment["schema"])
            provenance_init(experiment["provenance"])

            run_benchmark(db_name, experiment["name"],
                        run, experiment["scale"], experiment["updates"], experiment["provenance"] != "none")

def main() -> None:
    run_experiment()

if __name__ == "__main__":
    main()
