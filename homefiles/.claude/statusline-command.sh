#!/bin/bash

input=$(cat)

# Extract fields
model=$(echo "$input" | jq -r '.model.display_name // "Unknown"')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
output_style=$(echo "$input" | jq -r '.output_style.name // "default"')

# ANSI colors (using $'...' so variables contain actual ESC bytes)
RESET=$'\033[0m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
CYAN=$'\033[36m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
MAGENTA=$'\033[35m'
BLUE=$'\033[34m'
WHITE=$'\033[37m'

# Cost calculation (approximate, using Claude pricing)
model_id=$(echo "$input" | jq -r '.model.id // ""')
if echo "$model_id" | grep -qi "opus"; then
  input_cost_per_m=15.0
  output_cost_per_m=75.0
elif echo "$model_id" | grep -qi "haiku"; then
  input_cost_per_m=0.80
  output_cost_per_m=4.0
else
  # sonnet
  input_cost_per_m=3.0
  output_cost_per_m=15.0
fi

cost=$(echo "$total_input $total_output $input_cost_per_m $output_cost_per_m" | \
  awk '{printf "%.4f", ($1 / 1000000 * $3) + ($2 / 1000000 * $4)}')

# Context progress bar
BAR_WIDTH=20
if [ -n "$used_pct" ]; then
  filled=$(echo "$used_pct $BAR_WIDTH" | awk '{printf "%d", int($1 / 100 * $2 + 0.5)}')
  empty=$((BAR_WIDTH - filled))
  bar=""
  for i in $(seq 1 $filled); do bar="${bar}█"; done
  for i in $(seq 1 $empty);  do bar="${bar}░"; done

  # Color the bar based on usage
  if [ "$(echo "$used_pct > 80" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    bar_color="$RED"
  elif [ "$(echo "$used_pct > 50" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
    bar_color="$YELLOW"
  else
    bar_color="$GREEN"
  fi
  ctx_bar="${bar_color}${bar}${RESET}"
  ctx_label=$(echo "$used_pct" | awk '{printf "%.1f%%", $1}')
else
  ctx_bar="${DIM}$(printf '░%.0s' $(seq 1 $BAR_WIDTH))${RESET}"
  ctx_label="--.--%"
fi

# Effort/output style display
if [ "$output_style" != "default" ] && [ "$output_style" != "null" ] && [ -n "$output_style" ]; then
  effort_str=" ${MAGENTA}✦ ${output_style}${RESET}"
else
  effort_str=""
fi

echo "${CYAN}🤖 ${BOLD}${model}${RESET}${effort_str}  ${YELLOW}💰 \$${cost}${RESET}  ${BLUE}📊 [${ctx_bar}${BLUE}] ${WHITE}${ctx_label}${RESET}"
