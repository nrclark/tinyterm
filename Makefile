VERSION := 1.2
OUTPUT := tinyterm-$(VERSION)-py3-none-any.whl
SOURCES := setup.py $(wildcard tinyterm/*)

all: $(OUTPUT)

$(OUTPUT): dist/$(OUTPUT)
	cp $< $@

dist/$(OUTPUT): $(SOURCES) Makefile
	python3 setup.py bdist_wheel

clean:
	rm -rf tinyterm.egg-info
	rm -rf dist build
	rm -rf $(OUTPUT)
