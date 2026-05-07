# bondcalc is a molecular bond strength calculator


It uses a simple calculation for a set of 25 small molecules. This is for the purpose of demonstrating 
multi-container workload processing.


This demonstration will not work in the absence of an MSE544-built "Azure FunctionApp" API for pulling 
data from the periodic table. In brief: Set up an Azure VM as a workstation, use VS Code Server to 
connect, build a NoSQL database on Azure using Cosmos DB, put that behind an Azure Function App API, 
build a Docker image from a dockerfile, publish that to DockerHub, and run the script on the VM that
spawns 25 containers from that image. When they are done (results will be in `~/bondcalc_output`)
the `aggregate.py` program is run to combine the results into a single summary json file `results.json`. 
