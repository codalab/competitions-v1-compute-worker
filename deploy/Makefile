accept_keys:
	ANSIBLE_HOST_KEY_CHECKING=false ansible-playbook keys_accept.yaml

local_deploy:
    ansible-playbook --connection=local -i 127.0.0.1, mount.yaml --ask-become-pass

ad_hoc:
	ansible -m ping 
	ansible -m shell -a "echo ok, boomer"