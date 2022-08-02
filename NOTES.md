# Squidge
Fondly named after squee-g, the cleaning robot, and the sound of cleaning vandal grime :)

## TODO
- Connection to Discord
  - ABXY server
- Connection to MediaWiki software
  - Inkipedia EN
- Detect likely spam using wiki logs & report on Discord
  - Alert admins; potentially delete & block offenders
- Link permissions between Discord and the target wiki, such that some actions require Discord authentication
  - We could do this in a variety of ways:
    - Role assignments
    - Semi-hardcoded table: data that can be reloaded on the fly
    - Wiki page of known users
    - Discord integration of some sort - investigation needed
- Commands on Discord to make mass changes such as:
  - Auto-fix double and broken redirects where possible
  - Moving categories (and recategorising everything in the old category to the new name), 
  - Moving files (and updating references)
  - Creating a file archive for exporting a category
  - Auto-link to related articles using text that is already on the page, that has not yet been linked
  - Tag files that have bad names 
  - Tag mainspace pages that have no images or gallery
  - Autolink interwiki pages based on official translations (Splatoon FR, ES)
- Answer knowledge based questions such as "how much does x cost in Splatoon 3"
- Get stats on active editors esp around wiki staff

## Implementation ideas

We can use [SightEngine](https://sightengine.com/text-moderation-api) for text NSFW detection:

```shell
$ curl -X POST 'https://api.sightengine.com/1.0/text/check.json' \
>   -F 'text=Contact rick123(at)gmail(dot)com to have s_*_x' \
>   -F 'lang=en' \
>   -F 'mode=standard'
```
Response:
```shell
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  1249    0   868  100   381   3098   1359 --:--:-- --:--:-- --:--:--  4476
```
```json
{
    "status": "success",
    "request": {
        "id": "req_cjOXaoM24qDuqPsAFBfyE",
        "timestamp": 1659396691.064559,
        "operations": 1
    },
    "profanity": {
        "matches": [
            {
                "type": "sexual",
                "intensity": "medium",
                "match": "sx",
                "start": 41,
                "end": 45
            }
        ]
    },
    "personal": {
        "matches": [
            {
                "type": "email",
                "match": "rick123(at)gmail(dot)com",
                "start": 8,
                "end": 31
            }
        ]
    },
    "link": {
        "matches": [
            {
                "type": "url",
                "category": null,
                "match": "gmail(dot)com",
                "start": 19,
                "end": 31
            }
        ]
    }
}
```