from __future__ import division

import os
import numpy as np

from .. import units

from .qmbase import QMBase
from ..qmtmpl import QMTmpl


class MOPAC(QMBase):

    QMTOOL = 'MOPAC'

    def get_qm_system(self, embed):
        """Load QM information."""

        super(MOPAC, self).get_qm_system(embed)

        self._n_real_qm_atoms = self.qm_atoms.n_real_atoms
        self._n_virt_qm_atoms = self.qm_atoms.n_virt_atoms

    def get_mm_system(self, embed):
        """Load MM information."""

        super(MOPAC, self).get_mm_system(embed)

        self._n_mm_atoms = self.mm_atoms_near.n_atoms
        self._mm_position = self.mm_atoms_near.position
        self._qm_esp = embed.qm_esp_near
        self._qm_efield_near = embed.qm_efield_near

        if self.mm_atoms_far.charge_eeq is not None:
            raise NotImplementedError()
            self._qm_esp_far = embed.qm_esp_far
            self._qm_efield_far = embed.qm_efield_far

    def get_qm_params(self, method=None, **kwargs):
        """Get the parameters for QM calculation."""

        super(MOPAC, self).get_qm_params(**kwargs)

        if method is not None:
            self.method = method
        else:
            raise ValueError("Please set method for MOPAC.")

    def gen_input(self):
        """Generate input file for QM software."""

        qmtmpl = QMTmpl(self.QMTOOL)

        if self.calc_forces:
            calc_forces = 'GRAD '
        else:
            calc_forces = ''

        if self.addparam is not None:
            if isinstance(self.addparam, list):
                addparam = "".join([" %s" % i for i in self.addparam])
            else:
                addparam = " " + self.addparam
        else:
            addparam = ''

        nproc = self.get_nproc()

        with open(self.basedir + "mopac.mop", 'w') as f:
            f.write(qmtmpl.gen_qmtmpl().substitute(method=self.method,
                    charge=self.charge, calc_forces=calc_forces,
                    addparam=addparam, nproc=nproc))
            f.write("NAMD QM/MM\n\n")
            for i in range(self._n_qm_atoms):
                f.write(" ".join(["%6s" % self._qm_element[i],
                                  "%22.14e 1" % self._qm_position[i, 0],
                                  "%22.14e 1" % self._qm_position[i, 1],
                                  "%22.14e 1" % self._qm_position[i, 2], "\n"]))

        with open(self.basedir + "mol.in", 'w') as f:
            f.write("\n")
            f.write("%d %d\n" % (self._n_real_qm_atoms, self._n_virt_qm_atoms))

            for i in range(self._n_qm_atoms):
                f.write(" ".join(["%6s" % self._qm_element[i],
                                    "%22.14e" % self._qm_position[i, 0],
                                    "%22.14e" % self._qm_position[i, 1],
                                    "%22.14e" % self._qm_position[i, 2],
                                    " %22.14e" % (self._qm_esp[i]), "\n"]))

    def gen_cmdline(self):
        """Generate commandline for QM calculation."""

        cmdline = "cd " + self.basedir + "; "
        cmdline += "mopac mopac.mop 2> /dev/null"

        return cmdline

    def rm_guess(self):
        """Remove save from previous QM calculation."""

        pass

    def parse_output(self):
        """Parse the output of QM calculation."""

        output = self.load_output(self.basedir + "mopac.aux")

        self.get_qm_energy(output)
        self.get_qm_charge(output)
        self.get_qm_force(output)
        self.get_mm_force()

        self.qm_atoms.qm_energy = self.qm_energy * units.E_AU
        self.qm_atoms.qm_charge = self.qm_charge
        self.qm_atoms.force = self.qm_force * units.F_AU
        self.mm_atoms_near.force = self.mm_force * units.F_AU

    def get_qm_energy(self, output=None):
        """Get QM energy from output of QM calculation."""

        if output is None:
            output = self.load_output(self.basedir + "mopac.aux")

        for line in output:
            if "TOTAL_ENERGY" in line:
                self.qm_energy = float(line[17:].replace("D", "E")) / units.EH_TO_EV
                break

        return self.qm_energy

    def get_fij_near(self):
        """Get pair-wise forces between QM atomic charges and external point charges."""

        if not hasattr(self, 'qm_charge'):
            self.get_qm_charge()

        self.fij_near = -1 * self._qm_efield_near * self.qm_charge[np.newaxis, :, np.newaxis]

        return self.fij_near

    def get_qm_force(self, output=None):
        """Get QM forces from output of QM calculation."""

        if output is None:
            output = self.load_output(self.basedir + "mopac.aux")

        n_lines = int(np.ceil(self._n_qm_atoms * 3 / 10))

        for i in range(len(output)):
            if "GRADIENTS" in output[i]:
                gradients = np.array([])
                for line in output[(i + 1):(i + 1 + n_lines)]:
                    gradients = np.append(gradients, np.fromstring(line, sep=' '))
                break

        self.qm_force = -1 * gradients.reshape(self._n_qm_atoms, 3)

        if not hasattr(self, 'fij_near'):
            self.get_fij_near()

        self.qm_force -= self.fij_near.sum(axis=0)

        self.qm_force /= units.F_AU

        return self.qm_force

    def get_mm_force(self):
        """Get external point charge forces from output of QM calculation."""

        if not hasattr(self, 'fij_near'):
            self.get_fij_near()

        self.mm_force = self.fij_near.sum(axis=1) / units.F_AU

        return self.mm_force

    def get_qm_charge(self, output=None):
        """Get Mulliken charges from output of QM calculation."""

        if output is None:
            output = self.load_output(self.basedir + "mopac.aux")

        n_lines = int(np.ceil(self._n_qm_atoms / 10))

        for i in range(len(output)):
            if "ATOM_CHARGES" in output[i]:
                charges = np.array([])
                for line in output[(i + 1):(i + 1 + n_lines)]:
                    charges = np.append(charges, np.fromstring(line, sep=' '))
                break

        self.qm_charge = charges

        return self.qm_charge
