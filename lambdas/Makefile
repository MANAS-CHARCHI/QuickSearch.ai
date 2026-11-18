.PHONY: up build validate start-api start-lambda test-clean test-virus test-vlm test-sqli test-prompt-injection unit-test

up:
	cd .. && docker compose up -d --build db redis clamav minio

validate:
	sam validate --lint

build:
	sam build

start-api:
	sam local start-api --port 3001 --env-vars env.json --docker-network vault_network --warm-containers EAGER

start-lambda:
	sam local start-lambda --port 3002 --env-vars env.json --docker-network vault_network --warm-containers EAGER

test-clean:
	sam local invoke FileScanAndExtractFunction -e events/clean_document_event.json --env-vars env.json --docker-network vault_network

test-virus:
	sam local invoke FileScanAndExtractFunction -e events/eicar_virus_event.json --env-vars env.json --docker-network vault_network

test-vlm:
	sam local invoke ImageVLMDescriptionFunction -e events/image_vlm_event.json --env-vars env.json

test-sqli:
	sam local invoke TextSecurityAndVectorizeFunction -e events/sqli_payload_event.json --env-vars env.json --docker-network vault_network

test-prompt-injection:
	sam local invoke TextSecurityAndVectorizeFunction -e events/prompt_injection_event.json --env-vars env.json --docker-network vault_network

unit-test:
	python3 -m unittest discover -s tests -p "test_*.py" -v
