# YAML schema reference

The current document version is `1`. Unknown fields are rejected so misspellings do not silently change a card.

## Top-level fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `version` | integer | yes | Must be `1`. |
| `card` | mapping | yes | Title, metadata, and footer notes. |
| `canvas` | mapping | no | Fixed dimensions, background, and outer padding. |
| `theme` | mapping | no | Colors, borders, and typography. |
| `layout` | mapping | no | Grid and text-fitting defaults. |
| `ingredients` | mapping | dependency or geometry mode | Ingredient declarations. |
| `actions` | mapping | dependency mode | Named results with inputs and instructions. |
| `final` | string | dependency mode | ID of the final action result. |
| `flow` | mapping | alternate | Nested final-action-rooted recipe tree. |
| `stages` | mapping or list | geometry mode | Process columns in left-to-right order. |
| `steps` | list | geometry mode | Compact explicit process rectangles. |
| `rows` | list | alias | Expanded alternative to `ingredients`. |
| `cells` | list | alias | Expanded alternative to `steps`. |
| `notes` | list of strings | no | Additional footer notes after `card.footer`. |

Use one authoring mode: the recommended `ingredients` + `actions` + `final` dependency map, nested `flow`, or explicit geometry. Geometry mode requires exactly one of `ingredients` or `rows`, `stages`, and exactly one of `steps` or `cells`. Modes cannot be mixed.

## `card`

`title` is a required, non-empty string. `subtitle` and `source` default to empty strings. `footer` defaults to an empty list; each entry is wrapped and rendered beneath the grid.

## `canvas`

`width` and `height` are optional positive integers. An omitted width is calculated as outer horizontal padding plus the ingredient column and every stage. An omitted height is calculated from the measured header, row heights, measured footer, and vertical padding. A fixed dimension smaller than the calculated minimum is invalid.

`background` is a CSS hex color and overrides `theme.background`. `padding` accepts non-negative `top`, `right`, `bottom`, and `left` integers; defaults are `32`, `40`, `30`, and `40`.

## `theme`

| Field | Default |
| --- | --- |
| `border_color` | `#4b9847` |
| `border_width` | `6` |
| `outer_border_width` | unset; use normal deduplicated edges |
| `cell_background` | `#ffffff` |
| `background` | `#fffde8` |
| `text_color` | `#111111` |
| `secondary_text_color` | `#4a4a4a` |
| `font_family` | `[DejaVu Sans, Arial, sans-serif]` |
| `title_size` | `56` |
| `subtitle_size` | `28` |
| `cell_text_size` | `30` |
| `footer_size` | `23` |

Colors accept `#RGB`, `#RGBA`, `#RRGGBB`, or `#RRGGBBAA`. Generated pages and optional SVG exports contain only a font-family fallback list; they do not fetch external font resources. `outer_border_width`, when set, draws a complete grid perimeter at that width.

## `layout`

| Field | Default | Constraint |
| --- | ---: | --- |
| `ingredient_column_width` | automatic | optional positive fixed override |
| `ingredient_column_min_width` | 500 | positive automatic lower bound |
| `ingredient_column_max_width` | 640 | positive automatic upper bound |
| `default_stage_width` | 280 | positive |
| `row_height` | 72 | positive minimum for auto-sized rows |
| `title_height` | 145 | positive minimum |
| `footer_height` | 75 | non-negative minimum when notes exist |
| `cell_padding` | 16 | non-negative |
| `text_line_spacing` | 1.12 | positive multiplier |
| `min_font_size` | 18 | positive |

When `ingredient_column_width` is omitted, the renderer measures the widest ingredient label at `theme.cell_text_size`, adds horizontal cell padding, and clamps the result to the configured minimum and maximum. The title and footer areas grow when wrapped content needs more room. `row_height` is the minimum for rows without an explicit height; `default_stage_width` applies to stages without a width override.

## `ingredients` + `actions` + `final` (recommended)

Ingredients are declared once as `ingredient_id: label`. Each action mapping key names the result it produces, `from` names one input or a list of inputs, and `do` contains its instruction. `final` names the last action result:

```yaml
ingredients:
  pasta: 12 oz pasta
  tomatoes: 2 cups tomatoes
  stock: 1 cup stock
  garnish: chopped parsley

actions:
  cooked_pasta:
    from: pasta
    do: cook until al dente

  sauce:
    from: [tomatoes, stock]
    do: simmer until thick

  combined:
    from: [cooked_pasta, sauce]
    do: stir together

  serve:
    from: [combined, garnish]
    do: top and serve

final: serve
```

Action declaration order has no semantic effect. The compiler follows references backward from `final`; the order of IDs within each `from` list determines branch and ingredient-row order. Unknown references, cycles, IDs disconnected from `final`, and duplicate ingredient/action IDs are errors.

Geometry uses the same inference rules as nested flow: action depth determines its stage, descendant ingredients determine its vertical span, shorter branches receive waiting cells, and action text determines bounded stage width. Action nodes accept `stage_width`, `font_size`, `min_font_size`, `font_weight`, `align`, `valign`, and `padding` in addition to `from` and `do`.

One result cannot currently feed multiple later actions because tabular notation has no unambiguous arrowless split. Such fan-out fails validation with a suggestion to use explicit geometry.

## `flow` (nested alternate)

`flow` is a mapping containing exactly one final action root. Every node key is its stable ID. Scalar nodes are ingredient leaves; action nodes contain `do` and a non-empty `from` mapping:

```yaml
flow:
  serve:
    do: top and serve
    from:
      combined:
        do: stir together
        from:
          cooked_pasta:
            do: cook until al dente
            from:
              pasta: 12 oz pasta
          sauce:
            do: simmer until thick
            from:
              tomatoes: 2 cups tomatoes
              stock: 1 cup stock
      garnish: chopped parsley
```

The compiler derives geometry deterministically:

1. Depth-first leaf order becomes top-to-bottom ingredient order.
2. Ingredients occupy conceptual depth zero.
3. An action's stage is one greater than the deepest child stage.
4. An action spans the first through last ingredient leaf in its subtree.
5. If a child finishes more than one stage before its parent, an empty waiting cell fills the intervening columns.
6. Each inferred stage width is measured from its action text and clamped between half of `layout.default_stage_width` and the full default. `stage_width` on an action fixes the width for that inferred depth.

Action nodes accept `do`, `from`, `stage_width`, `font_size`, `min_font_size`, `font_weight`, `align`, `valign`, and `padding`. An ingredient normally uses a scalar label; a fixed height can use the expanded leaf form:

```yaml
stock:
  ingredient: 2 cups vegetable stock
  height: 90
```

Flow is intentionally a strict tree, not a general graph: node IDs must be unique, and shared intermediate results are not referenced from multiple parents. Use explicit geometry mode when a card requires DAG-like sharing, overlays, or manual spans.

## `ingredients` (geometry mode)

Each mapping key is the stable row reference and its value is the displayed label. Mapping order is top to bottom. Labels may use YAML block scalars to preserve desired line breaks.

```yaml
ingredients:
  stock: |-
    2 cups
    vegetable stock
```

Rows grow automatically from `layout.row_height` to fit their ingredient label. Process cells that need more vertical room distribute that extra space evenly among the automatic rows they span. For the uncommon case of a fixed row height, use a mapping value:

```yaml
ingredients:
  stock:
    label: 2 cups vegetable stock
    height: 90
```

## `stages` (geometry mode)

Each compact mapping key is the stage reference and its value is its positive width. Mapping order is left to right. A null value uses `layout.default_stage_width`. Width indicates visual room, not elapsed cooking time.

```yaml
stages:
  prep: 240
  simmer: 320
  serve:
```

## `steps` (geometry mode)

Every step requires `stage` and `rows`. A single ID occupies one stage or row; `start..end` denotes an inclusive span that must follow document order. `text` defaults to an empty string, which makes waiting cells concise. Step IDs are generated by list position (`step_1`, `step_2`, …); `id` is optional.

| Optional field | Default | Values |
| --- | --- | --- |
| `id` | generated | valid stable ID |
| `text` | empty string | string |
| `font_size` | `theme.cell_text_size` | positive integer |
| `min_font_size` | `layout.min_font_size` | positive integer no larger than `font_size` |
| `font_weight` | `normal` | `normal`, `bold`, or `100` through `900` |
| `align` | `center` | `left`, `center`, `right` |
| `valign` | `middle` | `top`, `middle`, `bottom` |
| `padding` | `layout.cell_padding` | non-negative integer |
| `allow_overlap` | `false` | boolean |

For example, this step spans three stages and two ingredient rows:

```yaml
- stage: mix..reduce
  rows: tomatoes..stock
  text: simmer until thick
```

An empty waiting branch needs only its geometry:

```yaml
- stage: prep..hold
  rows: garnish
```

Two steps overlap only if their inclusive row-index ranges and inclusive stage-index ranges both intersect. Geometric edge contact is valid. Set `allow_overlap: true` on either participating step only when an overlay is deliberate.

Unless a process cell has an explicit `font_size`, the renderer uses one largest shared size that fits every ingredient and process cell. Ingredients and instructions therefore use consistent typography across the entire grid.

## Expanded geometry compatibility syntax

Existing documents may use `rows` with repeated `id`, `label`, and optional `height` fields; list-form `stages` with `id` and optional `width`; and `cells` with `id`, `stage_start`, `stage_end`, and `rows.from`/`rows.to`. Compact and expanded section names cannot be mixed for the same concern. Both forms normalize to the same typed model and receive identical validation and rendering.
