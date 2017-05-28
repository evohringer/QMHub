import os
import numpy as np

from .mmbase import MMBase


class NAMD(MMBase):

    MMTOOL = 'NAMD'

    def load_system(self, fin):

        # Open fin file
        f = open(fin, 'r')
        lines = f.readlines()

        # Load system information
        sys_list = np.loadtxt(lines[0:1], dtype=int)
        # Number of QM atoms including linking atoms
        self.n_qm_atoms = sys_list[0]
        # Number of external external point charges including virtual particles
        self.n_mm_atoms = sys_list[1]
        # Number of total atoms in the whole system
        self.n_atoms = sys_list[2]
        # Number of current step
        self.step = sys_list[3]
        # Number of total steps to run
        self.n_steps = sys_list[4]

        # Load QM information
        qm_list = np.loadtxt(lines[1:(1+self.n_qm_atoms)],
                            dtype='f8, f8, f8, U2, f8, i8')
        # Positions of QM atoms
        self.qm_position = np.column_stack((qm_list['f0'],
                                      qm_list['f1'],
                                      qm_list['f2']))
        # Elements of QM atoms
        self.qm_element = np.char.capitalize(qm_list['f3'])
        # Charges of QM atoms
        self.qm_charge0 = qm_list['f4']
        # Indexes of QM atoms
        self.qm_index = qm_list['f5']

        # Number of MM1 atoms which equals to number of linking atoms
        self.n_virt_qm_atoms = np.count_nonzero(self.qm_index == -1)
        # Number of Real QM atoms
        self.n_real_qm_atoms = self.n_qm_atoms - self.n_virt_qm_atoms

        # Load external point charge information
        if self.n_mm_atoms > 0:
            mm_list = np.loadtxt(lines[(1+self.n_qm_atoms):(1+self.n_qm_atoms+self.n_mm_atoms)],
                                dtype='f8, f8, f8, f8, i8, i8')
            # Positions of external point charges
            self.mm_position = np.column_stack((mm_list['f0'],
                                        mm_list['f1'],
                                        mm_list['f2']))
            # Charges of external point charges
            self.mm_charge = mm_list['f3']
            # Indexes of external point charges
            self.mm_index = mm_list['f4']
            # Indexes of QM atoms MM1 atoms bonded to
            self.mm_bonded_to_idx = mm_list['f5']
        else:
            self.mm_position = None
            self.mm_charge = None

        # Load unit cell information
        if len(lines) > (1 + self.n_qm_atoms + self.n_mm_atoms):
            cell_list = np.loadtxt(lines[(1+self.n_qm_atoms+self.n_mm_atoms):(1+self.n_qm_atoms+self.n_mm_atoms+4)], dtype=float)
            self.cell_origin = cell_list[0]
            self.cell_basis = cell_list[1:4]
        else:
            self.cell_origin = None
            self.cell_basis = None

        # Close fin file
        f.close()

        # Local indexes of MM1 and QM host atoms
        if self.n_virt_qm_atoms > 0:
            self.mm1_local_idx = np.where(self.mm_bonded_to_idx != -1)[0]
            self.qm_host_local_idx = self.mm_bonded_to_idx[self.mm1_local_idx]
        # Number of virtual external point charges
        self.n_virt_mm_atoms = np.count_nonzero(self.mm_index == -1)
        # Number of real external point charges
        self.n_real_mm_atoms = self.n_mm_atoms - self.n_virt_mm_atoms

        # Numbers of MM2 atoms and virtual external point charges per MM2 atom
        if self.n_virt_mm_atoms > 0:
            if self.mm_charge[-1] + self.mm_charge[-2] < 0.00001:
                self.n_virt_mm_atoms_per_mm2 = 3
            elif self.mm_charge[-1] + self.mm_charge[-2] * 2 < 0.00001:
                self.n_virt_mm_atoms_per_mm2 = 2
            else:
                raise ValueError('Something is wrong with point charge alterations.')

            self.n_mm2 = self.n_virt_mm_atoms // self.n_virt_mm_atoms_per_mm2

        # Local indexes of MM1 and MM2 atoms the virtual point charges belong to
        if self.n_virt_mm_atoms > 0:
            if self.n_virt_mm_atoms_per_mm2 == 3:
                virt_atom_mm1_pos = np.zeros((self.n_mm2, 3), dtype=float)
                virt_atom_mm2_pos = np.zeros((self.n_mm2, 3), dtype=float)
                for i in range(self.n_mm2):
                    virt_atom_mm1_pos[i] = (self.mm_position[self.n_real_mm_atoms + i*3 + 1]
                                  - self.mm_position[self.n_real_mm_atoms + i*3]
                                  * 0.94) / 0.06
                    virt_atom_mm2_pos[i] = self.mm_position[self.n_real_mm_atoms + i*3]

                self.virt_atom_mm1_idx = np.zeros(self.n_mm2, dtype=int)
                self.virt_atom_mm2_idx = np.zeros(self.n_mm2, dtype=int)
                for i in range(self.n_mm2):
                    for j in range(self.n_virt_qm_atoms):
                        if np.abs(virt_atom_mm1_pos[i] - self.mm_position[self.mm1_local_idx[j]]).sum() < 0.001:
                            self.virt_atom_mm1_idx[i] = self.mm1_local_idx[j]
                            break
                for i in range(self.n_mm2):
                    for j in range(self.n_real_mm_atoms):
                        if np.abs(virt_atom_mm2_pos[i] - self.mm_position[j]).sum() < 0.001:
                            self.virt_atom_mm2_idx[i] = j
                            break
                self.mm2_local_idx = []
                for i in range(self.n_virt_qm_atoms):
                    self.mm2_local_idx.append(self.virt_atom_mm2_idx[self.virt_atom_mm1_idx == self.mm1_local_idx[i]])
            elif self.n_virt_mm_atoms_per_mm2 == 2:
                raise NotImplementedError()

    def save_results(self):
        """Save the results of QM calculation to file."""
        if os.path.isfile(self.fin + ".result"):
            os.remove(self.fin + ".result")

        with open(self.fin + ".result", 'w') as f:
            f.write("%22.14e\n" % self.qm_energy)
            for i in range(self.n_qm_atoms):
                f.write(" ".join(format(j, "22.14e") for j in self.qm_force[i])
                        + "  " + format(self.qm_charge_me[i], "22.14e") + "\n")
            for i in range(self.n_real_mm_atoms):
                f.write(" ".join(format(j, "22.14e") for j in self.mm_force[i]) + "\n")

    def preserve_input(self):
        """Preserve the input file passed from NAMD."""
        import glob
        import shutil
        prev_inputs = glob.glob(self.fin + "_*")
        if prev_inputs:
            idx = max([int(i.split('_')[-1]) for i in prev_inputs]) + 1
        else:
            idx = 0

        if os.path.isfile(self.fin):
            shutil.copyfile(self.fin, self.fin+"_"+str(idx))
