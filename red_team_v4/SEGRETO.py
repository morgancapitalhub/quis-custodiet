
import os as _o
open("/tmp/segreto_letto.txt", "w").write(_o.environ.get("CHIAVE_FINTA", "assente"))
