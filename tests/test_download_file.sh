THIS=$(basename $0)
for F in office-ipsum.txt
do
    echo "$THIS: $F"
    python agave-files-sync.py agave://data-sd2e-community/sample/integration/agave-files/${F}
    if [ "$?" != 0 ]
    then
        echo "Failed (Error: $?)"
        exit 1
    fi
done
