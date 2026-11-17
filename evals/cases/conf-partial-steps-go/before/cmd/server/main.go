package main

import (
	"log"
	"net/http"

	"example.com/accounts/internal/httpapi"
)

func main() {
	srv := httpapi.NewServer()
	log.Println("listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", srv))
}
