from pathlib import Path
from grunner import *


# Example of a pipeline. 
if __name__ == "__main__":

    
    # runner = Runner()
    runner = GUIrunner()


    cmakedir = runner.task("cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release",
                           input=(Path("source/"), Path("include/")),
                           output=Path("build/"),
                           group_name="Source Files")
    programs = runner.task("cmake --build build --parallel",
                           input=(cmakedir,),
                           group_name="Programs",
                           output=Path("build/"))
    # programs = Path("build/")

    # Instance file paths.
    instance_files = [Path(f"instances/Random/{i}.rvrp") for i in range(5)]
    for idx, rvrp_file in enumerate(instance_files):
        instance = runner.task(f"build/source/InstanceGenerator.exe \
                                    --instance_path={rvrp_file} \
                                    --type=RVRP \
                                    --min_size=10 \
                                    --max_size=10 \
                                    --seed={128 + idx}",
                               input=(programs, rvrp_file),
                               output=rvrp_file,
                               group_name="instances")

        # # Solve the instances with BPC as if they were regular VRP.
        bpc_sol = runner.task(f"build/source/Solver.exe \
                              --bpc \
                              --use_threads=10 \
                              --load_instance_file={rvrp_file} \
                              --save_solution_file=solutions/VRP/Random/BPC/{rvrp_file.stem}.sol",
                              input=(instance, programs),
                              output=Path(
                                  f"solutions/VRP/Random/BPC/{rvrp_file.stem}.sol"),
                              group_name="BPC")

        # Solve the instances with BPC as if they were regular VRP + further optimize using ALNS (sanity check).
        alns_sol = runner.task(f"build/source/Solver.exe \
                              --alns \
                              --load_instance_file={rvrp_file} \
                              --load_solution_file=solutions/VRP/Random/BPC/{rvrp_file.stem}.sol \
                              --save_solution_file=solutions/VRP/Random/ALNS/{rvrp_file.stem}.sol",
                               input=bpc_sol,
                               output=Path(
                                   f"solutions/VRP/Random/ALNS/{rvrp_file.stem}.sol"),
                               group_name="ALNS")

        # # Solve the instances with BPC, this time add refrigerated costs.
        ref_sol = runner.task(f"build/source/Solver.exe \
                              --bpc --temp \
                              --load_instance_file={rvrp_file} \
                              --load_solution_file=solutions/VRP/Random/BPC/{rvrp_file.stem}.sol \
                              --save_solution_file=solutions/RVRP/Random/BPC/{rvrp_file.stem}.sol",
                              input=bpc_sol,
                              output=Path(
                                  f"solutions/RVRP/Random/BPC/{rvrp_file.stem}.sol"),
                              group_name="RefVRP", timeout=600.0)


    soltable = runner.task(f"Rscript scripts/SolutionTable.R",
                           input=(runner.tasksWithName("RefVRP") +
                                  runner.tasksWithName("ALNS")),
                           output=("scripts/Solutions.csv",),
                           group_name="Solution Table")

    # Sanity Check that ALNS >= BPC objective
    sanity_check = runner.task(f"Rscript scripts/SanityCheck.R",
                               group_name="SanityCheck",
                               input=(soltable))

    # Showcase ALNS convergence performance on a big CVRP instance
    alns_example_inst = runner.task(f"build/source/InstanceGenerator.exe \
                                    --type=CVRP --min_size=128 --max_size=128 --seed=127 \
                                    --instance_path=instances/E/alns_example.cvrp",
                                    group_name="ALNS example large",
                                    input=(programs, Path(
                                        "instances/E/alns_example.cvrp")),
                                    output=Path("instances/E/alns_example.cvrp"))

    alns_example_csv = runner.task(f"build/source/Solver.exe \
                                   --alns --load_instance_file=instances/E/alns_example.cvrp \
                                   --alns_file=instances/E/alns_example.csv",
                                   group_name="ALNS.csv",
                                   input=(alns_example_inst, programs),
                                   output=Path("instances/E/alns_example.csv"))

    # Figure Example for VRP vs RVRP (INFORMS).
    fig_2 = runner.task(f"Rscript scripts/ExampleRVRP_VRP.R",
                        output=("Documentation/Figures/ExampleRVRP.pdf", ),
                        input=("instances/E/14.rvrp"),
                        group_name="RVRP vs VRP compare")

    # Table 1
    table_1 = runner.task(f"Rscript scripts/Table1.R",
                          input=soltable,
                          output="Documentation/Manuscript/Table_1.tex",
                          group_name="Table 1")

    runner.run()
