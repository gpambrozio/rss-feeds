##########################
### Development Tools  ###
##########################

.PHONY: dev_format
dev_format: ## Format Python code
	$(call check_venv)
	$(call print_info_section,Formatting Python code)
	$(Q)black .
	$(Q)isort .
	$(call print_success,Code formatted)

.PHONY: dev_test_feed
dev_test_feed: ## Run the test_feed.py script
	$(call check_venv)
	$(call print_info,Running test_feed.py)
	$(Q)python feed_generators/test_feed.py
	$(call print_success,Test feed completed)
