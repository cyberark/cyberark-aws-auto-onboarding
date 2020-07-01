#!/bin/sh

success=true
BTF=$(python3 dynamo_on_boarded.py)
echo "[INFO] There are $BTF successful records in dynamo table"
terraform init
terraform apply -auto-approve -var="region_main=$1" -var="region_sec=$2" -var="subnet_id_main=$3" -var="subnet_id_sec=$4" -var="key_pair_main=$5" -var="key_pair_sec=$6"
echo "[INFO] Finish deploy terraform"
ATF=$(terraform state list | grep aws_instance | wc -l)
echo "[INFO] terraform deployed $ATF instances"
DS=$(($BTF + $ATF))
CS=$(python3 dynamo_on_boarded.py)
echo "[INFO] Check if AOB succeed to on board all $ATF instances"
i=0
while [ $DS -gt $CS ]
do
	echo "[INFO] There are $CS of $DS successful records"
	i=$((i+1))
	if [ $i -eq 5 ]; then
		echo "[ERR] failed to on board all the instances"
		success=false
		break
	fi
	sleep 10
	CS=$(python3 dynamo_on_boarded.py)
done
terraform destroy -auto-approve -var="region_main=$1" -var="region_sec=$2" -var="subnet_id_main=$3" -var="subnet_id_sec=$4" -var="key_pair_main=$5" -var="key_pair_sec=$6"
CS=$(python3 dynamo_on_boarded.py)
i=0
while [ $CS -gt $BTF ]
do
	echo "[INFO] there are $CS of $BTF successful records"
	if [ $i -eq 5 ]; then
		echo "[ERR] AOB failed to delete all the instances"
		success=false
		break
	fi
	sleep 10
	CS=$(python3 dynamo_on_boarded.py)
done
if [ $success != true ]; then
	echo "[ERR] AOB stress test failed check for errors"
	exit 1
fi
echo "[INFO] AOB stress test succeed"
exit 0
