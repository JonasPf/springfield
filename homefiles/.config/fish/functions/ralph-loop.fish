function ralph-loop --description "Run the Ralph Wiggum loop until ALL_TASKS_DONE or max iterations reached"
    argparse 'max-iterations=!_validate_int --min 1' -- $argv
    or begin
        echo "Usage: ralph-loop [--max-iterations N]"
        return 1
    end

    set -l max_iter $_flag_max_iterations
    if test -z "$max_iter"
        set max_iter 50
    end

    set -l iteration 0

    while test $iteration -lt $max_iter
        set iteration (math $iteration + 1)
        echo "=== Ralph Wiggum Loop: iteration $iteration / $max_iter ==="

        set -l output (cat ~/prompts/SPECKIT-RALPH-LOOP.md | claude 2>&1)
        echo "$output"

        if string match -q '*ALL_TASKS_DONE*' -- "$output"
            echo "=== ALL_TASKS_DONE received after $iteration iteration(s). Exiting. ==="
            return 0
        end
    end

    echo "=== Max iterations ($max_iter) reached without ALL_TASKS_DONE. ==="
    return 1
end
