function simple-ralph-loop --description "Run the Ralph Wiggum loop indefinitely, feeding SPECKIT-RALPH-LOOP.md to claude"
    while true
        cat ~/prompts/SPECKIT-RALPH-LOOP.md | claude
    end
end
