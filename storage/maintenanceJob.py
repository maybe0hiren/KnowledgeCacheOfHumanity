# storage/maintenanceJob.py  (after change)
from redEngine.api.app import mom              # reuse the singleton

def runMaintenance():
    report = mom.maintenance()
    print(report.summary())                    # richer output than before
    return report