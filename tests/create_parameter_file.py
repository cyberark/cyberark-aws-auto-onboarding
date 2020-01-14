import yaml
import describe_resources


def CloudFormation_parameters_yml_generator(yml, obj):
    mod_yml = yaml.dump(yml)
    mod_yml = yaml.safe_load(mod_yml)
    mod_yml['PvwaIP'] = obj.ip
    mod_yml['ComponentsVPC'] = obj.vpc_id
    mod_yml['PVWASG'] = obj.group_id
    mod_yml['ComponentsSubnet'] = obj.subnet_id
    return mod_yml


def Runtime_parameters_yml_generator(yml, obj):
    mod_yml = yaml.dump(yml)
    mod_yml = yaml.safe_load(mod_yml)
    mod_yml['Accounts'] = obj.account_id
    mod_yml['Regions'] = 'ap-northeast-1'
    return mod_yml


def main():
    with open("deployment/vars/AOB-Params.yml") as param_file:
        try:
            yml = yaml.safe_load(param_file)
            for k, v in yml.items():
                if k == 'CloudFormation_parameters':
                    PvwaObj = describe_resources.main()
                    yml['CloudFormation_parameters'] = CloudFormation_parameters_yml_generator(v, PvwaObj)
                elif k == 'Runtime_parameters':
                    yml['Runtime_parameters'] = Runtime_parameters_yml_generator(v, PvwaObj)
                elif k == 'CFTemplatePath':
                    yml['CFTemplatePath'] = 'dist/multi-region/multi_region_main_cf_0.1.1.json'
                elif k == 'SSTemplatePath':
                    yml['SSTemplatePath'] = 'dist/multi-region/multi_region_stack_set_0.1.1.json'

        except yaml.YAMLError as exc:
            print(exc)
        with open("AOB-Params.yml", "w") as final_yml:
            yaml.dump(yml, final_yml)


main()
