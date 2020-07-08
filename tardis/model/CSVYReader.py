import numpy as np
import pandas as pd
import astropy.units as u

from collections import OrderedDict
from pyne import nucname
from tardis.io.parsers import csvy

class CSVYReader():

    def __init__(self, csvy_path):
        self.yml = csvy.load_yaml_from_csvy(csvy_path)
        self.csv = csvy.load_csv_from_csvy(csvy_path)

        return

    def to_csvy(self, fname):
        with open(fname, 'w') as f:
            f.write('---\n')
            for key in self.yml.keys():
                if not key == 'datatype':
                    f.write(key + ': ' + str(self.yml[key]) + '\n')
                elif key == 'datatype':
                    f.write('datatype:\n')
                    f.write('  fields:\n')
                    for field_dict in self.yml['datatype']['fields']:
                        f.write('    - name: %s\n'%(field_dict['name']))
                        if 'unit' in field_dict:
                            f.write('      unit: %s\n'%(field_dict['unit']))
                        if 'desc' in field_dict:
                            f.write('      desc: %s\n'%(field_dict['desc']))
            f.write('---\n')

            self.csv.to_csv(path_or_buf=f, index=False)
            f.close()

    def insert_shell_to_csv(self, velocity):
        shell_velocity = self.csv['velocity'].values
        ind_insert = np.searchsorted(shell_velocity, velocity, side='left')
        row_len = self.csv.shape[1]
        new_row = pd.Series(np.zeros(row_len), index=self.csv.columns, name=self.csv.shape[0])
        self.csv = self.csv.append(new_row)
        self.csv.iloc[ind_insert+1:,:] = self.csv.iloc[ind_insert:-1,:].values
        self.csv.iloc[ind_insert] = np.zeros(row_len)
        self.csv['velocity'].iloc[ind_insert] = velocity
        return

    def add_field_to_csv(self, fieldname, desc, unit=None, loc=None):
        if loc is None: loc = self.csv.shape[1]
        self.csv.insert(loc=loc, column=fieldname, value=np.zeros(self.csv.shape[0]))
        yml_odict = OrderedDict()
        yml_odict['name'] = fieldname
        if not unit is None:
            yml_odict['unit'] = unit
        yml_odict['desc'] = desc
        self.yml['datatype']['fields'].insert(loc, yml_odict)
        return


    def inject_element(self, element, mass):
        abund_names = [name for name in self.csv.columns
                       if nucname.iselement(name) or nucname.isnuclide(name)]

        element_Z = nucname.name_zz[element]

        if not element in abund_names:
            self.add_field_to_csv(fieldname=element, desc=element+' abundance', unit=None, loc=None)


        injected_mass = 0 * u.Msun
        injection_index = self.csv.shape[0] - 1

        # check if converting the next shell to desired element
        # will not yet reach the desired injection mass. If so,
        # proceed to convert next shell to desired element.
        # Loop does not run when next shell would overshoot
        # desired injection mass. This is a special case where
        # a fraction of the next shell must be converted and
        # the velocity structure modified.

        while (injected_mass.value + self.shell_masses[injection_index - 1].value < mass.value):
            # modify the abundance dataframe
            print(injection_index)

            for el in abund_names:
                self.csv.loc[injection_index, el] = 0.0
            self.csv.loc[injection_index, element] = 1.0


            #update the injected mass
            injected_mass = injected_mass + self.shell_masses[injection_index - 1]

            # update the injection index
            injection_index = injection_index - 1

        # handle the edge case of the last shell where
        # only a fraction of the shell is converted to
        # injection element.
        last_density = self.csv['density'][injection_index] * self.shell_density.unit
        last_v_outer = self.velocity[injection_index]
        last_r_outer = self.time * last_v_outer

        mass_diff = mass - injected_mass

        new_r_outer = (last_r_outer**3 - 3 / (4 * np.pi * last_density) * mass_diff.to('g'))**(1.0/3.0)
        new_v_outer = new_r_outer / self.time
        new_v_outer = new_v_outer.to(self.velocity.unit)

        self.csv['velocity'][injection_index] = new_v_outer
        self.insert_shell_to_csv(last_v_outer.value)
        self.csv.iloc[injection_index + 1] = self.csv.iloc[injection_index].values
        self.csv.iloc[injection_index + 1]['velocity'] = last_v_outer.value

        for el in abund_names:
            self.csv.loc[injection_index + 1, el] = 0.0
        self.csv.loc[injection_index + 1, element] = 1.0

        return


    @property
    def velocity(self):
        velocity_field_index = [field['name'] for field in self.yml['datatype']['fields']].index('velocity')
        velocity_unit = u.Unit(self.yml['datatype']['fields'][velocity_field_index]['unit'])
        velocity = self.csv['velocity'].values * velocity_unit
        return velocity

    @property
    def v_outer(self):
        return self.velocity[1:]

    @property
    def v_inner(self):
        return self.velocity[:-1]

    @property
    def shell_density(self):
        density_field_index = [field['name'] for field in self.yml['datatype']['fields']].index('density')
        density_unit = u.Unit(self.yml['datatype']['fields'][density_field_index]['unit'])
        density = self.csv['density'].values * density_unit
        density = density[1:]
        return density

    @property
    def time(self):
        return self.yml['model_density_time_0'].to('s')

    @property
    def r_inner(self):
        return self.time * self.v_inner

    @property
    def r_outer(self):
        return self.time * self.v_outer

    @property
    def shell_volumes(self):
        return ((4. / 3) * np.pi * (self.r_outer ** 3 - self.r_inner ** 3)).cgs

    @property
    def shell_masses(self):
        shell_masses = self.shell_volumes * self.shell_density
        shell_masses = shell_masses.to('Msun')
        return shell_masses