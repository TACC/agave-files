THIS=$(basename $0)
for D in good-directory good-directory-with-an-empty near-empty-directory empty-directory
do
    echo "$THIS: $D"
    python agave-files-sync.py --recursive agave://data-sd2e-community/sample/integration/agave-files/$D
    if [ "$?" != 0 ]
    then
        echo "Failed (Error: $?)"
        exit 1
    fi
done
