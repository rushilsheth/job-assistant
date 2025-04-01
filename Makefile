install:
	./install.sh
run_notion_server:
	./run_notion_server.sh
python_install:
	poetry lock
	poetry install