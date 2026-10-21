# Runtime and environment notes

> **Data availability boundary:** Offline verification without a simulator is possible only after obtaining the complete raw-data archive and release manifest. This public repository may not yet contain those components.

The original experiments use Python with the versions in the included `requirements-lock.txt` and `requirements-b5-vm.txt` files. The confirmatory engine includes Dockerfiles for the shared-airtime benchmark and ns-3 WiGig simulator, plus example VM execution scripts. The fresh Kubernetes extension requires a suitable Kubernetes cluster, `kubectl`, Docker/image access, and the pinned Python dependencies.

The archived raw outputs and offline verification are available without provisioning the simulator or Kubernetes cluster. Full reruns are resource-intensive; the reviewer should run the offline verifier first.
