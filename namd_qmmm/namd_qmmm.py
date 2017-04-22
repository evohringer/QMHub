import os
import sys
import numpy as np
from .qmtool import QM


class QMMM(object):
    def __init__(self, fin=None, qmElecEmbed='on', qmSwitching='off',
                 qmSwitchingType='shift', qmSoftware=None,
                 qmChargeMode="ff", qmCharge=None, qmMult=None,
                 qmCutoff=None, qmSwdist=None, PME='no', postproc='no'):
        """
        Creat a QMMM object.
        """
        self.qmElecEmbed = qmElecEmbed
        self.qmSwitching = qmSwitching
        self.qmSwitchingType = qmSwitchingType
        self.qmSoftware = qmSoftware
        self.qmChargeMode = qmChargeMode
        self.qmCharge = qmCharge
        self.qmMult = qmMult
        self.PME = PME
        self.postproc = postproc

        self.QM = QM(fin, self.qmSoftware, self.qmCharge, self.qmMult)

        if self.postproc.lower() == 'no':
            self.QM.calc_forces = 'yes'
        elif self.postproc.lower() == 'yes':
            self.QM.calc_forces = 'no'
        else:
            raise ValueError("Choose 'yes' or 'no' for 'postproc'.")

        if self.qmElecEmbed.lower() == 'on':
            if self.qmSwitching.lower() == 'on':
                if self.qmSwitchingType.lower() == 'shift':
                    self.qmCutoff = qmCutoff
                    self.QM.scale_charges(self.qmSwitchingType, self.qmCutoff)
                elif self.qmSwitchingType.lower() == 'switch':
                    self.qmCutoff = qmCutoff
                    self.qmSwdist = qmSwdist
                    self.QM.scale_charges(self.qmSwitchingType, self.qmCutoff, self.qmSwdist)
                elif self.qmSwitchingType.lower() == 'lrec':
                    self.qmCutoff = qmCutoff
                    self.QM.scale_charges(self.qmSwitchingType, self.qmCutoff)
                else:
                    raise ValueError("Only 'shift', 'switch', and 'lrec' are supported currently.")
        elif self.qmElecEmbed.lower() == 'off':
            self.QM.zero_pntChrgs()
        else:
            raise ValueError("Need a valid value for 'qmElecEmbed'.")

    def get_namdinput(self):
        """Get the path of NAMD input file (Unfinished)."""
        self.pid = os.popen("ps -p %d -oppid=" % os.getpid()).read().strip()
        self.cmd = os.popen("ps -p %s -ocommand=" % self.pid).read().strip().split()
        self.cwd = os.popen("pwdx %s" % self.pid).read().strip().split()[1]

    def run_qm(self, **kwargs):
        """Run QM calculation."""
        self.QM.get_qmparams(**kwargs)
        self.QM.run()
        if self.QM.exitcode != 0:
            sys.exit(self.QM.exitcode)

    def parse_output(self):
        """Parse the output of QM calculation."""
        if hasattr(self.QM, 'exitcode'):
            self.QM.get_qmenergy()
            if self.postproc.lower() == 'no':
                self.QM.get_qmforces()
                self.QM.get_pntchrgforces()
                self.QM.get_qmchrgs()
                self.QM.get_pntesp()

                if self.qmSwitching.lower() == 'on':
                    self.QM.corr_pntchrgscale()

                if self.PME.lower() == 'yes':
                    self.QM.corr_pbc()

                self.QM.corr_vpntchrgs()
            else:
                self.QM.qmForces = np.zeros((self.QM.numQMAtoms, 3))
                self.QM.pntChrgForces = np.zeros((self.QM.numRPntChrgs, 3))
        else:
            raise ValueError("Need to run_qm() first.")

    def save_results(self):
        """Save the results of QM calculation to file."""
        if hasattr(self.QM, 'qmEnergy'):
            if os.path.isfile(self.QM.fin+".result"):
                os.remove(self.QM.fin+".result")

            if self.qmChargeMode == "qm":
                outQMChrgs = self.QM.qmChrgs
            elif self.qmChargeMode == "ff":
                outQMChrgs = self.QM.qmChrgs0
            elif self.qmChargeMode == "zero":
                outQMChrgs = np.zeros(self.QM.numQMAtoms)

            with open(self.QM.fin + ".result", 'w') as f:
                f.write("%22.14e\n" % self.QM.qmEnergy)
                for i in range(self.QM.numQMAtoms):
                    f.write(" ".join(format(j, "22.14e") for j in self.QM.qmForces[i])
                            + "  " + format(outQMChrgs[i], "22.14e") + "\n")
                for i in range(self.QM.numRPntChrgs):
                    f.write(" ".join(format(j, "22.14e") for j in self.QM.pntChrgForces[i]) + "\n")
        else:
            raise ValueError("Need to parse_output() first.")

    def save_results_old(self):
        """Save the results of QM calculation to file (previous version)."""
        if os.path.isfile(self.QM.fin+".result"):
            os.remove(self.QM.fin+".result")

        if self.qmChargeMode == "qm":
            outQMChrgs = self.QM.qmChrgs
        elif self.qmChargeMode == "ff":
            outQMChrgs = self.QM.qmChrgs0
        elif self.qmChargeMode == "zero":
            outQMChrgs = np.zeros(self.QM.numQMAtoms)

        with open(self.QM.fin + ".result", 'w') as f:
            f.write("%22.14e\n" % self.QM.qmEnergy)
            for i in range(self.QM.numQMAtoms):
                f.write(" ".join(format(j, "22.14e") for j in self.QM.qmForces[i])
                        + "  " + format(outQMChrgs[i], "22.14e") + "\n")

    def save_extforces(self):
        """Save the MM forces to extforce.dat (previous version)."""
        if os.path.isfile(self.QM.baseDir + "extforce.dat"):
            os.remove(self.QM.baseDir + "extforce.dat")
        self.mmForces = np.zeros((self.QM.numAtoms, 3))
        self.mmForces[self.QM.pntIdx] = self.QM.pntChrgForces
        with open(self.QM.baseDir + "extforce.dat", 'w') as f:
            for i in range(self.QM.numAtoms):
                f.write("%4d    0  " % (i + 1)
                        + "  ".join(format(j, "22.14e") for j in self.mmForces[i]) +"\n")
            f.write("0.0")

    def save_pntchrgs(self):
        """Save the QM and MM charges to file (for debugging only)."""
        mmScale = np.zeros(self.QM.numAtoms)
        mmDist = np.zeros(self.QM.numAtoms)
        mmChrgs = np.zeros(self.QM.numAtoms)

        if hasattr(self.QM, 'pntScale'):
            mmScale[self.QM.pntIdx[0:self.QM.numRPntChrgs]] = self.QM.pntScale[0:self.QM.numRPntChrgs]
            mmDist[self.QM.pntIdx[0:self.QM.numRPntChrgs]] = self.QM.pntDist
        else:
            mmScale[self.QM.pntIdx[0:self.QM.numRPntChrgs]] += 1
        mmChrgs[self.QM.pntIdx[0:self.QM.numRPntChrgs]] = self.QM.outPntChrgs[0:self.QM.numRPntChrgs]

        if self.qmChargeMode == "qm":
            outQMChrgs = self.QM.qmChrgs
        elif self.qmChargeMode == "ff":
            outQMChrgs = self.QM.qmChrgs0
        elif self.qmChargeMode == "zero":
            outQMChrgs = np.zeros(self.QM.numQMAtoms)

        mmScale[self.QM.qmIdx[0:self.QM.numRealQMAtoms]] = np.ones(self.QM.numRealQMAtoms)
        mmChrgs[self.QM.qmIdx[0:self.QM.numRealQMAtoms]] = outQMChrgs[0:self.QM.numRealQMAtoms]

        np.save(self.QM.baseDir + "mmScale", mmScale)
        np.save(self.QM.baseDir + "mmDist", mmDist)
        np.save(self.QM.baseDir + "mmChrgs", mmChrgs)

    def preserve_input(self):
        """Preserve the input file passed from NAMD."""
        import glob
        import shutil
        listInputs = glob.glob(self.QM.fin + "_*")
        if listInputs:
            idx = max([int(i.split('_')[-1]) for i in listInputs]) + 1
        else:
            idx = 0

        if os.path.isfile(self.QM.fin):
            shutil.copyfile(self.QM.fin, self.QM.fin+"_"+str(idx))


if __name__ == "__main__":
    import sys

    qchem = QMMM(sys.argv[1], qmSwitching='on', qmSoftware='qchem',
                 qmChargeMode='ff', qmCharge=0, qmMult=1, qmCutoff=12.,
                 PME='yes')
    qchem.run_qm(method='hf', basis='6-31g', pop='pop_mulliken')
    qchem.parse_output()

    dftb = QMMM(sys.argv[1], qmSwitching='on', qmSoftware='dftb+',
                qmChargeMode='ff', qmCharge=0, qmMult=1, qmCutoff=12.,
                PME='yes')
    dftb.run_qm()
    dftb.parse_output()
