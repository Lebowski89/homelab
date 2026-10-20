// Offline Go-template execution only; no Alertmanager process or network access.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"text/template"
)

type Input struct {
	Payload any
	Data    any
}

func render(value any, data any) (any, error) {
	switch value := value.(type) {
	case string:
		funcs := template.FuncMap{
			"toUpper": strings.ToUpper,
			"toJson":  func(v any) (string, error) { b, e := json.Marshal(v); return string(b), e },
			"dict": func(v ...any) (map[string]any, error) {
				if len(v)%2 != 0 {
					return nil, fmt.Errorf("odd dict arguments")
				}
				result := map[string]any{}
				for i := 0; i < len(v); i += 2 {
					k, ok := v[i].(string)
					if !ok {
						return nil, fmt.Errorf("non-string key")
					}
					result[k] = v[i+1]
				}
				return result, nil
			},
		}
		t, err := template.New("").Option("missingkey=zero").Funcs(funcs).Parse(value)
		if err != nil {
			return nil, err
		}
		var out bytes.Buffer
		err = t.Execute(&out, data)
		return out.String(), err
	case map[string]any:
		out := map[string]any{}
		for k, v := range value {
			var e error
			out[k], e = render(v, data)
			if e != nil {
				return nil, e
			}
		}
		return out, nil
	default:
		return value, nil
	}
}
func main() {
	var in Input
	if e := json.NewDecoder(os.Stdin).Decode(&in); e != nil {
		panic(e)
	}
	out, e := render(in.Payload, in.Data)
	if e != nil {
		panic(e)
	}
	if e = json.NewEncoder(os.Stdout).Encode(out); e != nil {
		panic(e)
	}
}
