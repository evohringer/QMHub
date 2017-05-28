import os
import numpy as np

from ..qmbase import QMBase
from ..qmtmpl import QMTmpl


class DFTB(QMBase):

    QMTOOL = 'DFTB+'

    def get_qmparams(self, skfpath=None, **kwargs):
        """Get the parameters for QM calculation."""

        super(DFTB, self).get_qmparams(**kwargs)

        if skfpath is not None:
            self.skfpath = os.path.join(skfpath, '')
        else:
            raise ValueError("Please set skfpath for DFTB+.")

    def gen_input(self):
        """Generate input file for QM software."""

        qmtmpl = QMTmpl(self.QMTOOL)

        listElmnts = np.unique(self.qmElmnts).tolist()
        MaxAngularMomentum = "\n    ".join([i+" = "+qmtmpl.MaxAngularMomentum[i] for i in listElmnts])
        HubbardDerivs = "\n    ".join([i+" = "+qmtmpl.HubbardDerivs[i] for i in listElmnts])

        if self.pbc:
            KPointsAndWeights = qmtmpl.KPointsAndWeights
        else:
            KPointsAndWeights = ""

        if self.calc_forces:
            calcforces = 'Yes'
        else:
            calcforces = 'No'

        if self.read_guess:
            read_guess = 'Yes'
        else:
            read_guess = 'No'

        if self.addparam is not None:
            addparam = self.addparam
        else:
            addparam = ''

        with open(self.baseDir+"dftb_in.hsd", 'w') as f:
            f.write(qmtmpl.gen_qmtmpl().substitute(charge=self.charge,
                    numPntChrgs=self.numPntChrgs, read_guess=read_guess,
                    calcforces=calcforces, skfpath=self.skfpath,
                    MaxAngularMomentum=MaxAngularMomentum,
                    HubbardDerivs=HubbardDerivs,
                    KPointsAndWeights=KPointsAndWeights,
                    addparam=addparam))
        with open(self.baseDir+"input_geometry.gen", 'w') as f:
            if self.pbc:
                f.write(str(self.numQMAtoms) + " S" + "\n")
            else:
                f.write(str(self.numQMAtoms) + " C" + "\n")
            f.write(" ".join(listElmnts) + "\n")
            for i in range(self.numQMAtoms):
                f.write("".join(["%6d" % (i+1),
                                    "%4d" % (listElmnts.index(self.qmElmnts[i])+1),
                                    "%22.14e" % self.qmPos[i, 0],
                                    "%22.14e" % self.qmPos[i, 1],
                                    "%22.14e" % self.qmPos[i, 2], "\n"]))
            if self.pbc:
                f.write("".join(["%22.14e" % i for i in self.cellOrigin]) + "\n")
                f.write("".join(["%22.14e" % i for i in self.cellBasis[0]]) + "\n")
                f.write("".join(["%22.14e" % i for i in self.cellBasis[1]]) + "\n")
                f.write("".join(["%22.14e" % i for i in self.cellBasis[2]]) + "\n")

        with open(self.baseDir+"charges.dat", 'w') as f:
            for i in range(self.numPntChrgs):
                f.write("".join(["%22.14e" % self.pntPos[i, 0],
                                    "%22.14e" % self.pntPos[i, 1],
                                    "%22.14e" % self.pntPos[i, 2],
                                    " %22.14e" % self.pntChrgs4QM[i], "\n"]))

    def gen_cmdline(self):
        """Generate commandline for QM calculation."""

        nproc = self.get_nproc()
        cmdline = "cd " + self.baseDir + "; "
        cmdline += "export OMP_NUM_THREADS=%d; dftb+ > dftb.out" % nproc

        return cmdline

    def rm_guess(self):
        """Remove save from previous QM calculation."""

        qmsave = self.baseDir + "charges.bin"
        if os.path.isfile(qmsave):
            os.remove(qmsave)

    def get_qmenergy(self):
        """Get QM energy from output of QM calculation."""

        self.qmEnergy = np.genfromtxt(self.baseDir + "results.tag",
                                        dtype=float, skip_header=1,
                                        max_rows=1)

        return self.qmEnergy

    def get_qmforces(self):
        """Get QM forces from output of QM calculation."""

        self.qmForces = np.genfromtxt(self.baseDir + "results.tag",
                                        dtype=float, skip_header=5,
                                        max_rows=self.numQMAtoms)

        return self.qmForces

    def get_pntchrgforces(self):
        """Get external point charge forces from output of QM calculation."""

        self.pntChrgForces = np.genfromtxt(self.baseDir + "results.tag",
                                            dtype=float,
                                            skip_header=self.numQMAtoms+6,
                                            max_rows=self.numPntChrgs)

        return self.pntChrgForces

    def get_qmchrgs(self):
        """Get Mulliken charges from output of QM calculation."""

        if self.numQMAtoms > 3:
            self.qmChrgs = np.genfromtxt(
                self.baseDir + "results.tag", dtype=float,
                skip_header=(self.numQMAtoms + self.numPntChrgs
                                + int(np.ceil(self.numQMAtoms/3.)) + 14),
                max_rows=int(np.ceil(self.numQMAtoms/3.)-1.))
        else:
            self.qmChrgs = np.array([])
        self.qmChrgs = np.append(
            self.qmChrgs.flatten(),
            np.genfromtxt(self.baseDir + "results.tag", dtype=float,
                skip_header=(self.numQMAtoms + self.numPntChrgs
                                + int(np.ceil(self.numQMAtoms/3.))*2 + 13),
                max_rows=1).flatten())

        return self.qmChrgs

    def get_pntesp(self):
        """Get ESP at external point charges from output of QM calculation."""

        if not hasattr(self, 'qmChrgs'):
            self.get_qmchrgs()
        self.pntESP = np.sum(self.qmChrgs[np.newaxis, :] / self.dij, axis=1)

        return self.pntESP
