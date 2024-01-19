set windows-powershell := true

[private]
@default:
    just --list

# prepare venv and repo for developing
@bootstrap:
    pip install -r requirements/pre.txt
    pip install -e .
    pip install -r requirements/dev.txt
    pre-commit
    pre-commit install

# sync version of installed packages
@venv-sync:
    pip-sync requirements/pre.txt requirements/dev.txt
    pip install -e .

[private]
@setup-runner:
    pip install -r requirements/pre.txt
    pip install -r requirements/runner.txt

# run all linters
@lint:
    tox -e lint

# run basic tests on all python versions
@test:
    tox -e $(tox list --no-desc | grep '^py' | grep 'new$' | tr '\n' ',')

# run all tests on all python versions
@test-all-seq:
    tox -e $(tox list --no-desc | grep '^py' | sort -r | tr '\n' ',')

# run all tests on all python versions parallelly
@test-all:
    tox -e $(tox list --no-desc | grep '^py' | sort -r | tr '\n' ',') -p auto

# run all tests on specific python version
@test-on target:
    tox -e $(tox list --no-desc | grep '^{{ target }}' | sort -r | tr '\n' ',')

@cov:
    inv cov

@deps-compile:
    inv deps-compile

doc_source := "docs"
doc_target := "docs-build"

# build documentation
@doc:
    sphinx-build -M html {{ doc_source }} {{ doc_target }}
    echo "Open file://`pwd`/{{ doc_target }}/html/index.html"

# clean generated documentation and build cache
@doc-clean:
    sphinx-build -M clean {{ doc_source }} {{ doc_target }}
