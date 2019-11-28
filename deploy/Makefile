accept_keys:
	ANSIBLE_HOST_KEY_CHECKING=false ansible-playbook keys_accept.yaml

mount:
	ansible-playbook mount.yaml --tags "packages,configuration,mount"

deploy:
	ansible-playbook codalab-aci-worker.yaml --tags "packages,configuration,deploy"

local_mount:
	ansible-playbook --connection=local -i 127.0.0.1, mount.yaml --ask-become-pass

ad_hoc:
	ansible -m ping 
	ansible -m shell -a "echo ok, boomer"